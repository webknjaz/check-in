try:
    import pkg_resources
    __version__ = pkg_resources.require('check-in')[0].version
except Exception:
    __version__ = 'unknown'
