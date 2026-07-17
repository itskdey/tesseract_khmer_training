#!/usr/bin/env python3
"""Small desktop and CLI app for comparing two Tesseract Khmer models."""

from __future__ import annotations

import argparse
import os
import signal
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
BASE_MODEL = ROOT_DIR / "tessdata_best" / "khm.traineddata"
CUSTOM_MODEL = ROOT_DIR / "output" / "khm_custom.traineddata"
BACKUP_DIR = ROOT_DIR / "output" / "backups"


def latest_backup() -> Path | None:
    backups = list(BACKUP_DIR.glob("khm_custom-*.traineddata"))
    return max(backups, key=lambda path: path.stat().st_mtime) if backups else None


def default_before_model() -> Path:
    """Use the model immediately before the latest train-one run when possible."""
    return latest_backup() or BASE_MODEL


def run_ocr(model_path: Path, image_path: Path, psm: int) -> str:
    if not model_path.is_file():
        raise FileNotFoundError(f"Model not found: {model_path}")
    if not image_path.is_file():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with tempfile.TemporaryDirectory(prefix="khm-ocr-compare-") as temp_dir:
        tessdata_dir = Path(temp_dir)
        shutil.copy2(model_path, tessdata_dir / "comparison.traineddata")
        result = subprocess.run(
            [
                "tesseract",
                str(image_path),
                "stdout",
                "--tessdata-dir",
                str(tessdata_dir),
                "-l",
                "comparison",
                "--psm",
                str(psm),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    if result.returncode != 0:
        detail = result.stderr.strip() or "Tesseract returned an unknown error."
        raise RuntimeError(detail)
    return result.stdout.strip()


def edit_distance(expected: str, actual: str) -> int:
    """Return Unicode code-point Levenshtein distance."""
    previous = list(range(len(actual) + 1))
    for expected_index, expected_char in enumerate(expected, start=1):
        current = [expected_index]
        for actual_index, actual_char in enumerate(actual, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[actual_index] + 1,
                    previous[actual_index - 1]
                    + (expected_char != actual_char),
                )
            )
        previous = current
    return previous[-1]


def character_error_rate(expected: str, actual: str) -> float:
    if not expected:
        return 0.0 if not actual else 100.0
    return 100.0 * edit_distance(expected, actual) / len(expected)


def compare(
    image_path: Path,
    before_model: Path,
    after_model: Path,
    psm: int,
) -> tuple[str, str]:
    before_text = run_ocr(before_model, image_path, psm)
    after_text = run_ocr(after_model, image_path, psm)
    return before_text, after_text


def run_cli(args: argparse.Namespace) -> int:
    image_path = args.image.resolve()
    before_model = args.before_model.resolve()
    after_model = args.after_model.resolve()
    before_text, after_text = compare(
        image_path, before_model, after_model, args.psm
    )

    print(f"IMAGE:  {image_path}")
    print(f"BEFORE: {before_model}")
    print(f"AFTER:  {after_model}")
    print("\n===== BEFORE OCR =====")
    print(before_text)
    print("\n===== AFTER OCR =====")
    print(after_text)

    truth_path = args.truth
    if truth_path is None:
        automatic_truth = image_path.with_suffix(".gt.txt")
        truth_path = automatic_truth if automatic_truth.is_file() else None
    if truth_path is not None:
        truth = truth_path.read_text(encoding="utf-8").strip()
        print("\n===== GROUND TRUTH =====")
        print(truth)
        print("\n===== CHARACTER ERROR =====")
        print(f"Before: {character_error_rate(truth, before_text):.2f}%")
        print(f"After:  {character_error_rate(truth, after_text):.2f}%")
    return 0


def launch_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    try:
        from PIL import Image, ImageTk
    except ImportError:
        Image = None
        ImageTk = None

    class CompareApp:
        def __init__(self, root: tk.Tk) -> None:
            self.root = root
            self.root.title("Khmer OCR — Before / After")
            self.root.geometry("1120x760")
            self.root.minsize(850, 620)
            self.preview_photo = None
            self.just_trained = False
            self.active_process: subprocess.Popen[str] | None = None
            self.tool_buttons = []

            self.image_var = tk.StringVar()
            self.truth_var = tk.StringVar()
            self.before_var = tk.StringVar(value=str(default_before_model()))
            self.after_var = tk.StringVar(value=str(CUSTOM_MODEL))
            self.psm_var = tk.StringVar(value="13")
            self.iterations_var = tk.StringVar(value="2")
            self.learning_rate_var = tk.StringVar(value="0.00001")
            self.status_var = tk.StringVar(value="Choose an image to compare.")
            self.before_score_var = tk.StringVar(value="Before CER: —")
            self.after_score_var = tk.StringVar(value="After CER: —")
            self.tool_status_var = tk.StringVar(value="Ready.")
            self.full_iterations_var = tk.StringVar(value="10000")
            self.jobs_var = tk.StringVar(value="4")
            self.fast_limit_var = tk.StringVar(value="5000")
            self.batch_size_var = tk.StringVar(value="2000")

            self._build()
            self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        def _build(self) -> None:
            notebook = ttk.Notebook(self.root)
            notebook.pack(fill="both", expand=True)
            compare_tab = ttk.Frame(notebook)
            tools_tab = ttk.Frame(notebook)
            notebook.add(compare_tab, text="Compare & train one")
            notebook.add(tools_tab, text="Training tools")

            outer = ttk.Frame(compare_tab, padding=12)
            outer.pack(fill="both", expand=True)
            outer.columnconfigure(1, weight=1)

            self._path_row(outer, 0, "Image", self.image_var, self.choose_image)
            self._path_row(outer, 1, "Ground truth", self.truth_var, self.choose_truth)
            self._path_row(outer, 2, "Before model", self.before_var, self.choose_before)
            self._path_row(outer, 3, "After model", self.after_var, self.choose_after)

            controls = ttk.Frame(outer)
            controls.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(8, 8))
            ttk.Label(controls, text="Page mode (PSM):").pack(side="left")
            ttk.Combobox(
                controls,
                textvariable=self.psm_var,
                values=("6", "7", "11", "13"),
                width=5,
                state="readonly",
            ).pack(side="left", padx=(6, 12))
            self.run_button = ttk.Button(
                controls, text="Run comparison", command=self.start_comparison
            )
            self.run_button.pack(side="left")
            ttk.Separator(controls, orient="vertical").pack(
                side="left", fill="y", padx=12
            )
            ttk.Label(controls, text="Iterations:").pack(side="left")
            ttk.Entry(controls, textvariable=self.iterations_var, width=4).pack(
                side="left", padx=(5, 10)
            )
            ttk.Label(controls, text="Learning rate:").pack(side="left")
            ttk.Entry(controls, textvariable=self.learning_rate_var, width=10).pack(
                side="left", padx=(5, 10)
            )
            self.train_button = ttk.Button(
                controls, text="Train this image", command=self.start_training
            )
            self.train_button.pack(side="left")
            ttk.Label(controls, textvariable=self.status_var).pack(
                side="left", padx=14
            )

            self.preview = ttk.Label(
                outer,
                text="Image preview",
                anchor="center",
                relief="solid",
                padding=8,
            )
            self.preview.grid(
                row=5, column=0, columnspan=3, sticky="nsew", pady=(0, 10)
            )

            scores = ttk.Frame(outer)
            scores.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(0, 6))
            ttk.Label(scores, textvariable=self.before_score_var).pack(side="left")
            ttk.Label(scores, textvariable=self.after_score_var).pack(
                side="left", padx=24
            )

            results = ttk.Panedwindow(outer, orient="horizontal")
            results.grid(row=7, column=0, columnspan=3, sticky="nsew")
            outer.rowconfigure(7, weight=1)
            self.before_text = self._result_panel(results, "Before OCR")
            self.after_text = self._result_panel(results, "After OCR")
            self._build_training_tools(tools_tab)

        def _path_row(self, parent, row, label, variable, command) -> None:
            ttk.Label(parent, text=label).grid(
                row=row, column=0, sticky="w", padx=(0, 8), pady=3
            )
            ttk.Entry(parent, textvariable=variable).grid(
                row=row, column=1, sticky="ew", pady=3
            )
            ttk.Button(parent, text="Browse…", command=command).grid(
                row=row, column=2, padx=(8, 0), pady=3
            )

        def _result_panel(self, parent, title):
            frame = ttk.LabelFrame(parent, text=title, padding=8)
            text = tk.Text(frame, wrap="word", font=("Khmer Sangam MN", 16))
            scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
            text.configure(yscrollcommand=scrollbar.set)
            text.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            parent.add(frame, weight=1)
            return text

        def _build_training_tools(self, parent) -> None:
            outer = ttk.Frame(parent, padding=12)
            outer.pack(fill="both", expand=True)
            outer.columnconfigure(0, weight=1)
            outer.rowconfigure(3, weight=1)

            settings = ttk.LabelFrame(outer, text="Training settings", padding=10)
            settings.grid(row=0, column=0, sticky="ew", pady=(0, 10))
            self._setting_entry(
                settings, 0, "Full iterations", self.full_iterations_var, 10
            )
            self._setting_entry(settings, 1, "Parallel jobs", self.jobs_var, 6)
            self._setting_entry(settings, 2, "Fast subset", self.fast_limit_var, 8)
            self._setting_entry(settings, 3, "Batch size", self.batch_size_var, 8)

            actions = ttk.Frame(outer)
            actions.grid(row=1, column=0, sticky="ew")
            for column in range(4):
                actions.columnconfigure(column, weight=1)

            project = ttk.LabelFrame(actions, text="Project and data", padding=8)
            project.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
            self._tool_button(project, "Check tools", "check")
            self._tool_button(
                project,
                "Setup / update",
                "setup",
                confirmation="Download or update tesstrain and base models?",
            )
            self._tool_button(project, "Prepare raw scans", "prepare")
            self._tool_button(
                project,
                "Import archive XML",
                "import-archive",
                confirmation=(
                    "Importing clears existing generated PNG and .gt.txt output. "
                    "Continue?"
                ),
            )
            self._tool_button(project, "Validate ground truth", "validate")

            training = ttk.LabelFrame(actions, text="Training", padding=8)
            training.grid(row=0, column=1, sticky="nsew", padx=5)
            self._tool_button(
                training,
                "Full training",
                "train",
                overrides=self._full_overrides,
                confirmation="Full training can take many hours. Start it now?",
            )
            self._tool_button(
                training,
                "Fast training",
                "train-fast",
                overrides=self._fast_overrides,
                confirmation="Create a new fast subset and start training?",
            )
            self._tool_button(
                training,
                "Batch training",
                "train-batch",
                overrides=self._batch_overrides,
                confirmation="Create and train the next unused batch?",
            )
            self._tool_button(training, "Export model", "export")

            batches = ttk.LabelFrame(actions, text="Batch management", padding=8)
            batches.grid(row=0, column=2, sticky="nsew", padx=5)
            self._tool_button(
                batches, "Create batch", "batch", overrides=self._batch_overrides
            )
            self._tool_button(batches, "Batch status", "batch-status")
            self._tool_button(
                batches,
                "Finalize batch",
                "batch-finalize",
                confirmation="Mark the current pending batch as used?",
            )
            self._tool_button(
                batches,
                "Reset batch history",
                "batch-reset",
                confirmation="Reset all used-line batch history?",
            )

            utilities = ttk.LabelFrame(actions, text="Utilities", padding=8)
            utilities.grid(row=0, column=3, sticky="nsew", padx=(5, 0))
            self._tool_button(
                utilities,
                "Create fast subset",
                "fast-subset",
                overrides=self._fast_overrides,
            )
            self._tool_button(utilities, "Compare test_images", "compare")
            self._tool_button(
                utilities,
                "Clean training output",
                "clean",
                confirmation=(
                    "Delete generated checkpoints, lists, and temporary training "
                    "outputs? Exported backups are kept."
                ),
            )

            status = ttk.Frame(outer)
            status.grid(row=2, column=0, sticky="ew", pady=(10, 6))
            ttk.Label(status, textvariable=self.tool_status_var).pack(side="left")
            self.cancel_button = ttk.Button(
                status, text="Cancel running command", command=self.cancel_command
            )
            self.cancel_button.pack(side="right")
            self.cancel_button.configure(state="disabled")

            log_frame = ttk.LabelFrame(outer, text="Live command output", padding=8)
            log_frame.grid(row=3, column=0, sticky="nsew")
            self.tool_log = tk.Text(
                log_frame, wrap="word", font=("Menlo", 11), height=18
            )
            scrollbar = ttk.Scrollbar(
                log_frame, orient="vertical", command=self.tool_log.yview
            )
            self.tool_log.configure(yscrollcommand=scrollbar.set)
            self.tool_log.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

        @staticmethod
        def _setting_entry(parent, column, label, variable, width) -> None:
            ttk.Label(parent, text=label).grid(
                row=0, column=column * 2, sticky="w", padx=(0, 5)
            )
            ttk.Entry(parent, textvariable=variable, width=width).grid(
                row=0, column=column * 2 + 1, sticky="w", padx=(0, 18)
            )

        def _tool_button(
            self,
            parent,
            label: str,
            target: str,
            overrides=None,
            confirmation: str | None = None,
        ) -> None:
            button = ttk.Button(
                parent,
                text=label,
                command=lambda: self.start_make_command(
                    target, overrides, confirmation
                ),
            )
            button.pack(fill="x", pady=3)
            self.tool_buttons.append(button)

        @staticmethod
        def _positive_integer(value: str, label: str) -> int:
            number = int(value)
            if number <= 0:
                raise ValueError(f"{label} must be greater than zero.")
            return number

        def _full_overrides(self) -> dict[str, str]:
            iterations = self._positive_integer(
                self.full_iterations_var.get(), "Full iterations"
            )
            jobs = self._positive_integer(self.jobs_var.get(), "Parallel jobs")
            return {"MAX_ITERATIONS": str(iterations), "TESSTRAIN_JOBS": str(jobs)}

        def _fast_overrides(self) -> dict[str, str]:
            limit = self._positive_integer(self.fast_limit_var.get(), "Fast subset")
            return {"FAST_LIMIT": str(limit)}

        def _batch_overrides(self) -> dict[str, str]:
            size = self._positive_integer(self.batch_size_var.get(), "Batch size")
            return {"BATCH_SIZE": str(size)}

        def start_make_command(
            self,
            target: str,
            overrides=None,
            confirmation: str | None = None,
        ) -> None:
            if self.active_process is not None:
                messagebox.showwarning(
                    "Command already running", "Cancel or finish the current command first."
                )
                return
            try:
                values = overrides() if overrides is not None else {}
            except (TypeError, ValueError) as exc:
                messagebox.showerror("Invalid setting", str(exc))
                return
            if confirmation and not messagebox.askyesno("Confirm command", confirmation):
                return

            command = ["make", target]
            command.extend(f"{key}={value}" for key, value in values.items())
            self.tool_log.delete("1.0", "end")
            self._append_tool_log(f"$ {' '.join(command)}\n\n")
            self.tool_status_var.set(f"Running: make {target}")
            self._set_tool_busy(True)

            def worker() -> None:
                try:
                    process = subprocess.Popen(
                        command,
                        cwd=ROOT_DIR,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        bufsize=1,
                        start_new_session=True,
                    )
                    self.active_process = process
                    assert process.stdout is not None
                    for line in process.stdout:
                        self.root.after(0, lambda value=line: self._append_tool_log(value))
                    return_code = process.wait()
                    self.active_process = None
                    self.root.after(
                        0,
                        lambda: self.finish_make_command(target, return_code),
                    )
                except Exception as exc:
                    self.active_process = None
                    detail = str(exc)
                    self.root.after(0, lambda: self.fail_make_command(detail))

            threading.Thread(target=worker, daemon=True).start()

        def _append_tool_log(self, value: str) -> None:
            self.tool_log.insert("end", value)
            self.tool_log.see("end")

        def _set_tool_busy(self, busy: bool) -> None:
            state = "disabled" if busy else "normal"
            for button in self.tool_buttons:
                button.configure(state=state)
            self.cancel_button.configure(state="normal" if busy else "disabled")

        def finish_make_command(self, target: str, return_code: int) -> None:
            self._set_tool_busy(False)
            if return_code == 0:
                self.tool_status_var.set(f"Completed: make {target}")
                if target == "export":
                    self.after_var.set(str(CUSTOM_MODEL))
            else:
                self.tool_status_var.set(
                    f"Failed: make {target} (exit code {return_code})"
                )

        def fail_make_command(self, detail: str) -> None:
            self._set_tool_busy(False)
            self.tool_status_var.set("Command failed to start.")
            self._append_tool_log(f"\nERROR: {detail}\n")
            messagebox.showerror("Command failed", detail)

        def cancel_command(self) -> None:
            process = self.active_process
            if process is None:
                return
            if messagebox.askyesno("Cancel command?", "Stop the running command now?"):
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                    self.tool_status_var.set("Stopping command…")
                except ProcessLookupError:
                    pass

        def close_app(self) -> None:
            process = self.active_process
            if process is not None:
                close = messagebox.askyesno(
                    "Command is running",
                    "Closing the app will stop the running command. Close anyway?",
                )
                if not close:
                    return
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            self.root.destroy()

        def choose_image(self) -> None:
            selected = filedialog.askopenfilename(
                title="Choose image",
                filetypes=[
                    ("Images", "*.png *.jpg *.jpeg *.tif *.tiff *.bmp"),
                    ("All files", "*"),
                ],
            )
            if not selected:
                return
            self.image_var.set(selected)
            automatic_truth = Path(selected).with_suffix(".gt.txt")
            if automatic_truth.is_file():
                self.truth_var.set(str(automatic_truth))
            self.show_preview(Path(selected))

        def choose_truth(self) -> None:
            selected = filedialog.askopenfilename(
                title="Choose ground truth", filetypes=[("Ground truth", "*.gt.txt")]
            )
            if selected:
                self.truth_var.set(selected)

        def choose_before(self) -> None:
            self._choose_model(self.before_var)

        def choose_after(self) -> None:
            self._choose_model(self.after_var)

        def _choose_model(self, variable) -> None:
            selected = filedialog.askopenfilename(
                title="Choose traineddata model",
                filetypes=[("Tesseract model", "*.traineddata")],
            )
            if selected:
                variable.set(selected)

        def show_preview(self, image_path: Path) -> None:
            if Image is None or ImageTk is None:
                try:
                    photo = tk.PhotoImage(file=str(image_path))
                    factor = max(
                        1,
                        (photo.width() + 1049) // 1050,
                        (photo.height() + 209) // 210,
                    )
                    self.preview_photo = photo.subsample(factor)
                    self.preview.configure(image=self.preview_photo, text="")
                except Exception:
                    self.preview.configure(text=str(image_path), image="")
                return
            try:
                image = Image.open(image_path)
                image.thumbnail((1050, 210))
                self.preview_photo = ImageTk.PhotoImage(image)
                self.preview.configure(image=self.preview_photo, text="")
            except Exception as exc:
                self.preview.configure(text=f"Preview unavailable: {exc}", image="")

        def start_comparison(self) -> None:
            image_path = Path(self.image_var.get()).expanduser()
            before_model = Path(self.before_var.get()).expanduser()
            after_model = Path(self.after_var.get()).expanduser()
            try:
                psm = int(self.psm_var.get())
                if not image_path.is_file():
                    raise FileNotFoundError("Choose an image first.")
                if not before_model.is_file():
                    raise FileNotFoundError(f"Before model not found: {before_model}")
                if not after_model.is_file():
                    raise FileNotFoundError(f"After model not found: {after_model}")
            except Exception as exc:
                messagebox.showerror("Cannot compare", str(exc))
                return

            self.run_button.configure(state="disabled")
            self.status_var.set("Running Tesseract…")
            self.before_score_var.set("Before CER: —")
            self.after_score_var.set("After CER: —")
            truth_value = self.truth_var.get().strip()

            def worker() -> None:
                try:
                    before, after = compare(
                        image_path, before_model, after_model, psm
                    )
                    truth = None
                    if truth_value:
                        truth_path = Path(truth_value).expanduser()
                        truth = truth_path.read_text(encoding="utf-8").strip()
                    self.root.after(0, lambda: self.show_results(before, after, truth))
                except Exception as exc:
                    detail = str(exc)
                    self.root.after(0, lambda: self.show_error(detail))

            threading.Thread(target=worker, daemon=True).start()

        def start_training(self) -> None:
            image_path = Path(self.image_var.get()).expanduser()
            truth_path = Path(self.truth_var.get()).expanduser()
            try:
                if not image_path.is_file():
                    raise FileNotFoundError("Choose a PNG image first.")
                if image_path.suffix.lower() != ".png":
                    raise ValueError("Incremental training currently requires a PNG image.")
                if not truth_path.is_file():
                    raise FileNotFoundError("Choose the matching ground-truth file.")
                truth = truth_path.read_text(encoding="utf-8").strip()
                if not truth:
                    raise ValueError("Ground-truth text cannot be empty.")
                if len([line for line in truth.splitlines() if line.strip()]) > 1:
                    self.psm_var.set("6")
                iterations = int(self.iterations_var.get())
                learning_rate = float(self.learning_rate_var.get())
                if not 1 <= iterations <= 100:
                    raise ValueError("Iterations must be between 1 and 100.")
                if learning_rate <= 0:
                    raise ValueError("Learning rate must be greater than zero.")
            except Exception as exc:
                messagebox.showerror("Cannot train", str(exc))
                return

            confirmed = messagebox.askyesno(
                "Train custom model?",
                "This will update output/khm_custom.traineddata.\n\n"
                "The current model will be backed up automatically. Continue?",
            )
            if not confirmed:
                return

            self.run_button.configure(state="disabled")
            self.train_button.configure(state="disabled")
            self.status_var.set("Training this image…")

            def worker() -> None:
                try:
                    with tempfile.TemporaryDirectory(
                        prefix="khm-train-one-app-"
                    ) as temp_dir:
                        input_dir = Path(temp_dir)
                        shutil.copy2(image_path, input_dir / "sample.png")
                        (input_dir / "sample.gt.txt").write_text(
                            truth + "\n", encoding="utf-8"
                        )
                        environment = os.environ.copy()
                        environment.update(
                            {
                                "INPUT_DIR": str(input_dir),
                                "OUTPUT_DIR": str(ROOT_DIR / "output"),
                                "MODEL_NAME": "khm_custom",
                                "MAX_ITERATIONS": str(iterations),
                                "LEARNING_RATE": str(learning_rate),
                            }
                        )
                        result = subprocess.run(
                            [str(ROOT_DIR / "scripts" / "train_one.sh")],
                            cwd=ROOT_DIR,
                            env=environment,
                            check=False,
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                        )
                    if result.returncode != 0:
                        detail = (result.stdout + "\n" + result.stderr).strip()
                        raise RuntimeError(detail[-5000:])
                    backup = latest_backup()
                    self.root.after(0, lambda: self.finish_training(backup))
                except Exception as exc:
                    detail = str(exc)
                    self.root.after(0, lambda: self.show_error(detail))

            threading.Thread(target=worker, daemon=True).start()

        def finish_training(self, backup: Path | None) -> None:
            if backup is not None:
                self.before_var.set(str(backup))
            else:
                self.before_var.set(str(BASE_MODEL))
            self.after_var.set(str(CUSTOM_MODEL))
            self.just_trained = True
            self.train_button.configure(state="normal")
            self.status_var.set("Training complete; comparing before and after…")
            self.start_comparison()

        def show_results(self, before: str, after: str, truth: str | None) -> None:
            self._set_text(self.before_text, before)
            self._set_text(self.after_text, after)
            if truth is not None:
                before_score = character_error_rate(truth, before)
                after_score = character_error_rate(truth, after)
                self.before_score_var.set(f"Before CER: {before_score:.2f}%")
                self.after_score_var.set(f"After CER: {after_score:.2f}%")
            if self.just_trained:
                self.status_var.set("Training and comparison complete.")
                self.just_trained = False
            else:
                self.status_var.set("Comparison complete.")
            self.run_button.configure(state="normal")
            self.train_button.configure(state="normal")

        def show_error(self, detail: str) -> None:
            self.status_var.set("Comparison failed.")
            self.run_button.configure(state="normal")
            self.train_button.configure(state="normal")
            messagebox.showerror("Tesseract error", detail)

        @staticmethod
        def _set_text(widget, value: str) -> None:
            widget.delete("1.0", "end")
            widget.insert("1.0", value)

    root = tk.Tk()
    CompareApp(root)
    root.mainloop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", action="store_true", help="Run without the desktop UI.")
    parser.add_argument("image", nargs="?", type=Path, help="Image to compare in CLI mode.")
    parser.add_argument("--truth", type=Path, help="Optional matching ground-truth text.")
    parser.add_argument(
        "--before-model", type=Path, default=default_before_model()
    )
    parser.add_argument("--after-model", type=Path, default=CUSTOM_MODEL)
    parser.add_argument("--psm", type=int, default=13)
    args = parser.parse_args()
    if args.cli and args.image is None:
        parser.error("CLI mode requires an image path.")
    return args


def main() -> int:
    args = parse_args()
    if args.cli:
        return run_cli(args)
    launch_gui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
