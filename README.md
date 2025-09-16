# Shorts Maker

Shorts Maker generates vertical video clips from longer gameplay footage. The
script detects scenes, crops them to the desired aspect ratio and renders them
as ready‑to‑upload shorts.

## Features

- Automatic scene detection using `scenedetect`
- Smart cropping with optional blurred background for non‑vertical footage
- Retry logic during rendering to avoid spurious failures
- Configuration via a single `ProcessingConfig` dataclass
- Tested with `pytest`

## Requirements

- Python 3.10+
- FFmpeg (required by `moviepy`)
- See `requirements.txt` for Python dependencies

## Installation

```bash
pip install -r requirements.txt
```

If FFmpeg is not already installed on your system, refer to the
[MoviePy documentation](https://zulko.github.io/moviepy/install.html) for
installation instructions.

## Usage

1. Place source videos inside the `gameplay/` directory.
2. Run the script:

   ```bash
   python shorts.py
   ```

3. Generated clips are written to the `generated/` directory.


Environment variables from a `.env` file will be loaded automatically if
present.

## Docker

Build and run using Docker:

```bash
docker build -t shorts-maker .
docker run --rm \
    -v $(pwd)/gameplay:/app/gameplay \
    -v $(pwd)/generated:/app/generated \
    --env-file .env \
    shorts-maker
```

## Running Tests

Unit tests live in the `tests/` folder. Run them with:

```bash
pytest -q
```

## Acknowledgments

Thank the Binary-Bytes for the original code and idea: https://github.com/Binary-Bytes/Auto-YouTube-Shorts-Maker

## License

This project is released under the [Unlicense](LICENSE).
