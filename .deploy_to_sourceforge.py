import sys
import os
from pyrpl import sshshell, __version__


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python .deploy_to_sourceforge.py source destination")
    ssh = sshshell.SshShell(hostname='frs.sourceforge.net',
                            user=os.environ['SOURCEFORGE_USR'],
                            password=os.environ['SOURCEFORGE_PSW'],
                            shell=False,
                            timeout=10)
    source, dest = sys.argv[1], sys.argv[2]
    print("Uploading file '%s' to '%s' on sourceforge..." % (source, dest))
    try:
        ssh.scp.put(source, remote_path=dest, recursive=True)
    except BaseException as e:
        print("Upload of file '%s' to '%s' to sourceforge failed: %s!" % (source, dest, e))
        raise e
    else:
        print("Finished upload of file '%s' to '%s' on sourceforge!" % (source, dest))
