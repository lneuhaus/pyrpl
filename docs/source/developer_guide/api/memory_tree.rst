MemoryTree
***********

In general, Memory Tree is satisfactory.

Problems
------------

1. The MemoryBranch doesn't implement the full API
   of a dict. This is not nice because things like
   set\_setup\_attributes(\ **self.c) are not possible. I guess the
   reason is that a dict needs to implement some public methods such as
   keys(), values() iter()... and that's another argument to remove the
   support for point-notation. -> Of course, this full API is impossible
   to implement when one assumes all properties without leading
   underscore to be dictionary entries. If you want to use **, you
   should read the API documentation of memoryTree and do
   set\_setup\_attributes(\*\*self.c.\_dict)
