#!/usr/bin/python3

import jinja2
import pathlib
import shutil
import subprocess
import sys


###############
# Entry point #
###############
def main():
    base = pathlib.Path(sys.argv[0]).parent.parent
    templates = base / "share" / "templates"

    def requires(distribution, suite, package, unittest=False):
        args = [
            str(base / ".." / "share" / "requires.py"),
            "-d",
            distribution,
            "-s",
            suite,
            "-p",
            package,
            "-n",
        ]
        if unittest:
            args.append("-u")
        return subprocess.check_output(args).decode("utf-8").strip()

    # Create the environment
    env = jinja2.Environment(loader=jinja2.FileSystemLoader([str(templates)]))

    # Loop on all docker files
    print("Render templates:")
    for file in base.rglob("Dockerfile.jinja2"):
        print("* %s" % file)
        dockerfile = file.with_suffix("")
        data = file.read_text(encoding="utf-8")
        generated = env.from_string(data).render({"requires": requires}).strip()
        dockerfile.write_text(generated + "\n", encoding="utf-8")

    return 0


if __name__ == "__main__":
    sys.exit(main())
