"""Prevent an enhancement job from replacing its input or an existing result."""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import hashlib
from pathlib import Path


def check_output(source: str, destination: str) -> Path:
    input_path = Path(source)
    output = Path(destination)
    if input_path.resolve() == output.resolve() or (output.exists() and input_path.samefile(output)):
        raise FileExistsError(f"輸出不能覆寫原始影片：{output}")
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"輸出檔已存在，請換個檔名或資料夾：{output}")
    return output


@contextmanager
def reserve_output(destination: str):
    """A Windows mutex keeps both GUI and CLI jobs from sharing one parts folder."""
    normalized = str(Path(destination).resolve()).casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
    handle = kernel.CreateMutexW(None, True, f"Local\\VideoEnhance-{digest}")
    error = ctypes.get_last_error()
    if not handle:
        raise ctypes.WinError(error)
    try:
        if error == 183:  # ERROR_ALREADY_EXISTS
            raise FileExistsError(f"另一個工作正在處理這個輸出：{destination}")
        try:
            yield
        finally:
            kernel.ReleaseMutex(handle)
    finally:
        kernel.CloseHandle(handle)
