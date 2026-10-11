"""Paired immutable-generation CDP lease."""
from __future__ import annotations
import fcntl, os, stat
from pathlib import Path

class CdpLease:
    def __init__(self, root: Path, port: int)->None: self.root,self.port,self.fd=root,port,None
    def __enter__(self)->"CdpLease":
        info=self.root.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode)!=0o700: raise RuntimeError("unsafe CDP lock root")
        path=self.root/f"cdp-{os.getuid()}-{self.port}.lock"
        self.fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try: fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as e: os.close(self.fd); self.fd=None; raise RuntimeError("dedicated CDP endpoint is already in use") from e
        return self
    def __exit__(self,*_:object)->None:
        if self.fd is not None: fcntl.flock(self.fd,fcntl.LOCK_UN); os.close(self.fd); self.fd=None
