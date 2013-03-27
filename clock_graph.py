#!/usr/bin/env python

import os,sys
import getopt


adbcommand="adb shell %r "
#shellcommand='cd /d/clock/; for c in `ls`; do if [ -d $c ]; then echo $c :`su -c cat $c/parent` :`su -c cat $c/rate` :`su -c cat $c/refcnt`:`su -c cat $c/state` ; fi done'
shellcommand='cd /d/clock/; for c in `ls`; do if [ -d $c ]; then echo $c :`cat $c/parent` :`cat $c/rate` :`cat $c/refcnt`:` cat $c/state` ; fi done'

# basic check env.

help_for_install_adb = """
Error: Not found 'adb' in your execute environment.
Please install adb by android-sdk.
http://developer.android.com/tools/help/adb.html
http://developer.android.com/sdk/index.html
"""

help_for_install_dot = """
Error: not found 'dot' in your environment.
If you use ubuntu, do this to install the suit:
    sudo apt-get install graphviz

If you're using other system, please refer home site of graphviz to install:
    http://www.graphviz.org/
"""

usage_string = """
clock_graph.py is a tool can generate clock graphic of your system.
It's based on adb and needs your android device rooted.
This tool needs adb and grphviz.

About the diagram, you will see a depends clock relation ship diagram of clock tree,
the filled with gray clock is the currently enable clock, by it's "state" attribute
in clock debugfs.
the dotted clock is the clock currently not using, aka, "state" is 0.

In default, this script will filter out the clock not any clock's parent and not enable.
If you want to dump full state of clock, use -F or --full

Usage:
        python clock_graph.py -[vht] -f [png|jpg|ps|svg] -o output_file

-h, --help:
        show this message

-f, --format:
        the output image format, can support ps, png, jpg, and svg.(default svg).

-o, --output:
        the output image path, defaut out.svg

-F, --full:
        show all the clock's state

-v, --verbose:
        verbose output, will dump out all dot source etc.

Any bug report or suggestion, please mail me:
        Jason Zhang<jasozhang@nvidia.com>
"""

global verbose, output, output_format, tiny_graph
output = "out"
output_format = "svg"
verbose = False
tiny_graph = True



mount_command='adb shell "su -c mount -t debugfs nodev /sys/kernel/debug"'
check_mount_command='adb shell mount'

def check_mount():
    mountresult = os.popen(check_mount_command).read();
    mountresult = mountresult.split(' ')
    if "/sys/kernel/debug" in mountresult:
        if verbose:
            print "debugfs mount check pass..."
        return True
    else:
        return False

def try_mount_debugfs():
    os.popen(mount_command).read();

def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], "hvFo:f:", ["help", "verbose", "full", "output=", "format="])
    except getopt.GetoptError:
        print usage_string
        sys.exit()

    for opt,arg in opts:
        if opt in ("-h", "--help"):
            print usage_string
            sys.exit();
        elif opt in ("-v", "--verbose"):
            global verbose
            verbose = True
        elif opt in ("-o", "--output"):
            global output
            output = arg
        elif opt in ("-F", "--full"):
            global tiny_graph
            tiny_graph = False
        elif opt in ("-f", "--format"):
            global output_format
            output_format = arg
            if output_format not in ("png", "svg", "ps", "jgeg"):
                print "output format not recognize"
                print usage_string
                sys.exit()

    target_file_name = output
    if not output.endswith(output_format):
        target_file_name = output + "." + output_format


    not_have_adb = len(os.popen("which adb").read())
    if not_have_adb == 0:
        print help_for_install_adb
        sys.exit()

    
    not_have_dot = len(os.popen("which dot").read())
    if not_have_dot == 0:
        print help_for_install_dot
        sys.exit()
    
    if not check_mount():
        try_mount_debugfs()

    if not check_mount():
        print "Failed to mount debugfs"
        sys.exit()


    print "Start capture clock information";
    
    cpuinfocmd = "adb shell cat /proc/cpuinfo"
    versioncmd = "adb shell cat /proc/version"
    cpuinfo = os.popen(cpuinfocmd).read()
    versioninfo = os.popen(versioncmd).read()
    hardwareinfo = ""
    serialno = ""
    kernelversion = ""
    buildtime = ""

    lines = cpuinfo.split("\r\n")
    for l in lines:
        if len(l.split(":")) < 2:
            continue

        n,v = l.split(":");
        if n.strip() == "Hardware":
            hardwareinfo = v.strip()
        if n.strip() == "Serial":
            serialno = v.strip()

    lines = versioninfo.split(" ")

    kernelversion = kernelversion.join(lines[2:3])
    buildtime = " ".join(lines[-5:])
    buildtime = buildtime.strip()

    if verbose:
        print "Hardware: %s" % hardwareinfo
        print "SerialNo:%s" % serialno
        print "Kernel:%s" % kernelversion
        print "Build Time: %s" % buildtime

    if verbose:
        print adbcommand % shellcommand 

    rawresult = os.popen(adbcommand % shellcommand).read();

    if verbose:
        print rawresult 

    lines = rawresult.split("\r\n")

    dotsource = []

    dotsource.append('digraph clock {\n size="1000,1000";\n');
    rank={};

    # some note:

    dotsource.append('\t __note__ [label="Note:\\nHardware:%s\\nSerialNO:%s\\nKernel:%s\\nBuildTime:%s" shape=note style=filled fillcolor="#b4cf4c"];\n' % (hardwareinfo, serialno, kernelversion, buildtime));

    if verbose:
        print dotsource[-1] 

    # first pass, calc the rank and relation

    for l in lines:
        l = l.strip()
        member = l.split(":")
        if len(member) != 5:
            continue

        name = member[0].strip()
        parent = member[1].strip()
        state = int(member[4])
        
        if parent in  rank.keys():
            i = rank[parent]
            rank[parent] = i + 1
        else:
            rank[parent] = 1

    passed = {}

    for l in lines:
        l = l.strip();
        member = l.split(":");
        if len(member) != 5:
            break
        name = member[0].strip();
        parent = member[1].strip();
        state = int(member[4])
        refcnt = int(member[3])
        rate = int(member[2])
        
        if tiny_graph and state == 0 and name not in rank:
            if verbose: print "pass %s" % name
            passed[name] = refcnt
            continue
    # format of data, <name>:<parent>:<rate>:<refcnt>:<state>

        dotsource.append('\t"%s" [label="%s\\n %s" style=%s weight=%d shape=%s];\n '
                         % (name,
                            name,
                            "%d(%d)" % (rate, refcnt),
                            "filled" if state > 0 else "dashed",
                            rank[name] if name in rank else 1,
                            "box"
                            ));
        dotsource.append('\t"%s" -> "%s";\n' % (parent, name));

    dotsource.append("}");

    f = open('.out.dot', 'w')
    f.write( "".join(dotsource));
    f.close()

    ret  = os.system("dot .out.dot -T%s -o %s" % (output_format, target_file_name))
    if ret != 0:
        print "Error on generate diagram by dot, please check the dot's error log"
    else:
        print "Success generate clock diagram, please check it the %s." % target_file_name

    return ret;



if __name__ == "__main__":
    main(sys.argv)
