MemoryTree
***********

In general, Memory Tree is satisfactory. But a number of implementation
details make the code that uses the Tree sometimes rather ugly. Let's
collect examples for this here in order to find the API that allows for
the cleanest code.

1. from pyrpl.py: ``try:`` ``self.c.pyrpl.loglevel='info'``
   ``except KeyError:`` ``self.c["pyrpl"]=dict(loglevel='info')``

2. Also something very intriguing (not sure if it is designed to be this
   way or if it's a bug): p.c.scopes --> returns a MemoryBranch
   p.c["scopes"]--> returns a CommentedMap -> This is a bug!

3. To be honest, for simplicity, I would give up the support for
   point-notation and I would also enforce only one yaml library:
   ruamel.yml (even if it's not a standard one, this will make testing
   much more straight-forward).

-> Im against removing working code. But we can issue a deprecation
warning when ruamel is not used and say that support for this version is
suspended.

4. I also realized that the MemoryBranch doesn't implement the full API
   of a dict. This is not nice because things like
   set\_setup\_attributes(\ **self.c) are not possible. I guess the
   reason is that a dict needs to implement some public methods such as
   keys(), values() iter()... and that's another argument to remove the
   support for point-notation. -> Of course, this full API is impossible
   to implement when one assumes all properties without leading
   underscore to be dictionary entries. If you want to use **, you
   should read the API documentation of memoryTree and do
   set\_setup\_attributes(\*\*self.c.\_dict)
