import sys
import os
from pyrpl import sshshell, __version__


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python .deploy_to_sourceforge.py file1 [file2] ...")

    pw = os.environ['PYPI_PSW']
    ssh = sshshell.SshShell(hostname='frs.sourceforge.net',
                            user='lneuhaus',
                            password=pw,
                            shell=False)
    for filename in sys.argv[1:]:
        for destpath in ['/home/frs/project/pyrpl/',
                         '/home/frs/project/pyrpl/%s/' % __version__
                         ]:
            print("Uploading file '%s' to '%s' on sourceforge..." % (filename, destpath))
            try:
                ssh.scp.put(filename, destpath)
            except BaseException as e:
                print("Upload of file '%s' to '%s' to sourceforge failed: %s!" % (filename, destpath, e))
                ssh = sshshell.SshShell(hostname='frs.sourceforge.net',
                                        user='lneuhaus',
                                        password=pw,
                                        shell=False)
            else:
                print("Finished upload of file '%s' to '%s' on sourceforge!" % (filename, destpath))