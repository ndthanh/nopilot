"""Prevent two supported entrypoints writing the same nopilot data directory."""
import pathlib
import msvcrt
def default_directory(path):
    """Reuse an existing pre-rename data directory without moving user files."""
    current=pathlib.Path(path);legacy=pathlib.Path(str(path).replace('nopilot','kopilot'))
    return legacy if not current.exists() and legacy.exists() else current

class DataLock:
    def __init__(self,directory):
        root=pathlib.Path(directory).resolve();root.mkdir(parents=True,exist_ok=True)
        # Retain the lock filename so old and renamed entrypoints cannot overlap.
        self.file=(root/'.kopilot.lock').open('a+b');self.file.seek(0,2)
        if not self.file.tell():self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
        except OSError as error:self.file.close();raise RuntimeError('This data directory is already open in another nopilot process') from error
    def close(self):
        if not self.file.closed:self.file.seek(0);msvcrt.locking(self.file.fileno(),msvcrt.LK_UNLCK,1);self.file.close()
