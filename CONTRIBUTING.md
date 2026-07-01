# Contributing

Contributions are welcome, especially improvements to Khmer preprocessing,
ground-truth validation, training ergonomics, and documentation.

## Ground Truth Rules

- Do not submit fake Khmer text.
- Do not submit OCR output as final ground truth.
- Every `.gt.txt` must be manually verified against its matching line image.
- Do not commit private scans, copyrighted datasets, generated `.lstmf` files,
  or trained model outputs.

## Development

Run basic checks before opening a pull request:

```sh
make check
python3 -m py_compile scripts/*.py
bash -n scripts/*.sh
```

If you change training behavior, document the expected command and output path
in `README.md`.
