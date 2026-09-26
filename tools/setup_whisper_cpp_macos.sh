#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODEL_NAME="${1:-large-v3-turbo}"
WHISPER_CPP_DIR="${WHISPER_CPP_DIR:-"$ROOT/models/whisper_cpp"}"
SOURCE_DIR="${WHISPER_CPP_SOURCE_DIR:-"$WHISPER_CPP_DIR/source"}"
BUILD_DIR="${WHISPER_CPP_BUILD_DIR:-"$SOURCE_DIR/build"}"
BIN_DIR="$WHISPER_CPP_DIR/bin"
MODEL_FILE="${WHISPER_CPP_MODEL_FILE:-"$WHISPER_CPP_DIR/ggml-${MODEL_NAME}.bin"}"
COREML_ZIP="${WHISPER_CPP_COREML_ZIP:-"$WHISPER_CPP_DIR/ggml-${MODEL_NAME}-encoder.mlmodelc.zip"}"
COREML_DIR="${WHISPER_CPP_COREML_DIR:-"$WHISPER_CPP_DIR/ggml-${MODEL_NAME}-encoder.mlmodelc"}"
VAD_MODEL_FILE="${WHISPER_CPP_VAD_MODEL_FILE:-"$WHISPER_CPP_DIR/ggml-silero-v6.2.0.bin"}"
REPO_URL="${WHISPER_CPP_REPO_URL:-https://github.com/ggml-org/whisper.cpp.git}"
MODEL_URL="${WHISPER_CPP_MODEL_URL:-https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-${MODEL_NAME}.bin?download=true}"
COREML_URL="${WHISPER_CPP_COREML_URL:-https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-${MODEL_NAME}-encoder.mlmodelc.zip?download=true}"
VAD_MODEL_URL="${WHISPER_CPP_VAD_MODEL_URL:-https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin}"
ENABLE_METAL="${WHISPER_CPP_ENABLE_METAL:-1}"
ENABLE_COREML="${WHISPER_CPP_ENABLE_COREML:-1}"
DOWNLOAD_MODEL="${WHISPER_CPP_DOWNLOAD_MODEL:-1}"
DOWNLOAD_VAD="${WHISPER_CPP_DOWNLOAD_VAD:-1}"

require_command() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "[!] Missing required command: $1" >&2
        exit 1
    fi
}

logical_cpus() {
    sysctl -n hw.logicalcpu 2>/dev/null || printf "4"
}

require_command git
require_command cmake
require_command curl
if [ "$ENABLE_COREML" = "1" ]; then
    require_command unzip
fi

mkdir -p "$WHISPER_CPP_DIR" "$BIN_DIR"

if [ -d "$SOURCE_DIR/.git" ]; then
    echo "[*] Updating whisper.cpp source..."
    git -C "$SOURCE_DIR" pull --ff-only
else
    echo "[*] Cloning whisper.cpp..."
    git clone "$REPO_URL" "$SOURCE_DIR"
fi

echo "[*] Building whisper-cli..."
cache_source=""
if [ -f "$BUILD_DIR/CMakeCache.txt" ]; then
    cache_source="$(sed -n 's/^CMAKE_HOME_DIRECTORY:INTERNAL=//p' "$BUILD_DIR/CMakeCache.txt" | tail -n 1)"
fi
if [ -n "$cache_source" ] && [ "$cache_source" != "$SOURCE_DIR" ]; then
    echo "[*] Resetting stale CMake cache after checkout relocation..."
    rm -f "$BUILD_DIR/CMakeCache.txt"
    rm -rf "$BUILD_DIR/CMakeFiles"
fi

cmake_flags=(
    -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_BUILD_RPATH_USE_ORIGIN=ON
    '-DCMAKE_BUILD_RPATH=@loader_path'
)
if [ "$ENABLE_METAL" = "1" ]; then
    cmake_flags+=(-DGGML_METAL=ON)
fi
if [ "$ENABLE_COREML" = "1" ]; then
    cmake_flags+=(-DWHISPER_COREML=ON -DWHISPER_COREML_ALLOW_FALLBACK=ON)
fi
cmake -S "$SOURCE_DIR" -B "$BUILD_DIR" "${cmake_flags[@]}"
cmake --build "$BUILD_DIR" -j "$(logical_cpus)" --config Release

CLI_PATH="$BUILD_DIR/bin/whisper-cli"
if [ ! -x "$CLI_PATH" ] && [ -x "$BUILD_DIR/bin/Release/whisper-cli" ]; then
    CLI_PATH="$BUILD_DIR/bin/Release/whisper-cli"
fi
if [ ! -x "$CLI_PATH" ]; then
    echo "[!] whisper-cli was not built at expected path: $BUILD_DIR/bin/whisper-cli" >&2
    exit 1
fi

case "$CLI_PATH" in
    "$WHISPER_CPP_DIR"/*)
        CLI_LINK_TARGET="../${CLI_PATH#"$WHISPER_CPP_DIR"/}"
        ;;
    *)
        CLI_LINK_TARGET="$CLI_PATH"
        ;;
esac
ln -sfn "$CLI_LINK_TARGET" "$BIN_DIR/whisper-cli"

if [ -f "$MODEL_FILE" ]; then
    echo "[i] GGML model already exists: $MODEL_FILE"
elif [ "$DOWNLOAD_MODEL" != "1" ]; then
    echo "[i] Skipping GGML model download."
else
    echo "[*] Downloading GGML model: $MODEL_NAME"
    curl -L --fail --progress-bar "$MODEL_URL" -o "$MODEL_FILE.tmp"
    mv "$MODEL_FILE.tmp" "$MODEL_FILE"
fi

if [ "$ENABLE_COREML" = "1" ] && [ "$DOWNLOAD_MODEL" = "1" ]; then
    if [ -d "$COREML_DIR" ]; then
        echo "[i] CoreML encoder already exists: $COREML_DIR"
    else
        echo "[*] Downloading CoreML encoder: $MODEL_NAME"
        curl -L --fail --progress-bar "$COREML_URL" -o "$COREML_ZIP.tmp"
        mv "$COREML_ZIP.tmp" "$COREML_ZIP"
        unzip -q -o "$COREML_ZIP" -d "$WHISPER_CPP_DIR"
        rm -rf "$WHISPER_CPP_DIR/__MACOSX"
    fi
fi

if [ "$DOWNLOAD_VAD" = "1" ]; then
    if [ -f "$VAD_MODEL_FILE" ]; then
        echo "[i] Silero VAD model already exists: $VAD_MODEL_FILE"
    else
        echo "[*] Downloading Silero VAD model..."
        curl -L --fail --progress-bar "$VAD_MODEL_URL" -o "$VAD_MODEL_FILE.tmp"
        mv "$VAD_MODEL_FILE.tmp" "$VAD_MODEL_FILE"
    fi
fi

echo
echo "[OK] whisper.cpp is ready."
echo
echo "Add/update these lines in .env:"
echo "WHISPER_BACKEND=whisper_cpp"
echo "WHISPER_CPP_BINARY=$BIN_DIR/whisper-cli"
echo "WHISPER_CPP_MODELS_DIR=$WHISPER_CPP_DIR"
echo "WHISPER_CPP_MODEL_PATH=$WHISPER_CPP_DIR/ggml-{model}.bin"
echo "WHISPER_CPP_CONVERT_AUDIO=1"
echo "WHISPER_CPP_DOWNLOAD_COREML=1"
echo "# Silero VAD is installed automatically to suppress silence hallucinations."
