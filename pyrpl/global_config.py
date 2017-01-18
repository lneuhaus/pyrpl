from .memory import MemoryTree
import os.path

default_config_dir = os.path.join(os.path.dirname(__file__), 'config')
# global_config provides the MemoryTree associated with the global configuration file
global_config = MemoryTree(os.path.join(default_config_dir, 'global_config.yml'))
