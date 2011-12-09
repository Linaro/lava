import cgi
import os
import re
import markup

def getDispatcherErrors(logfile):
    if not logfile:
        return "Log file is missing"
    errors = ""
    for line in logfile:
        if line.find("CriticalError:") != -1 or \
           line.find("Lava failed on test:") != -1 :
            errors += line

    return errors

def getDispatcherLogSize(logfile):
    if not logfile:
        return 0
    else:
        logfile.seek(0, os.SEEK_END)
        size = logfile.tell()
        return size

def getDispatcherLogMessages(logfile):
    if not logfile:
        return "Log file is missing"

    logs = []
    log_prefix = '<LAVA_DISPATCHER>'
    level_pattern = re.compile('....-..-.. ..:..:.. .. ([A-Z]+):')
    for line in logfile:
        if not line.startswith(log_prefix):
            continue
        line = line[len(log_prefix):].strip()
        match = level_pattern.match(line)
        if not match:
            continue
        if len(line) > 90:
            line = line[:90] + '...'
        logs.append((match.group(1), line))
    return logs

def formatLogFileAsHtml(logfile):
    if not logfile:
        return "Log file is missing"

    page = markup.page(mode="xml")
    id_count = 0
    console_log = ""
    dispatcher_log = ""


    page.init()

    for line in logfile:
        if line.find("<LAVA_DISPATCHER>") != -1 or \
           line.find("lava_dispatcher") != -1 or \
           line.find("CriticalError:") != -1 :
            # close the previous log
            if len(dispatcher_log) > 0:
                dispatcher_log += line
                if len(console_log) > 0:
                    # dispatcher
                    page.div(id="%d"%id_count, class_="dispatcher_log")
                    page.a(name="%d"%id_count)
                    page.pre()
                    page.code(cgi.escape(dispatcher_log))
                    page.pre.close()
                    page.div.close()
                    dispatcher_log = ""

                    # console
                    # collapse ?
                    line_count = len(console_log.splitlines())
                    if line_count > 20:
                        page.div(id="%d"%id_count, class_="toggle_console_log")
                        page.a(cgi.escape("<"*30+"- Jump to next <LAVA_DISPATCHER> and skip over %3d lines -"%line_count+">"*30), href="#%d"%(id_count+1), _class="toggle_console_log")
                        page.div.close()

                    page.div(id="%d"%id_count, class_="console_log")
                    page.pre()
                    page.code(cgi.escape(console_log))
                    page.pre.close()
                    page.div.close()
                    console_log = ""
            else:
                id_count += 1
                dispatcher_log = line
        else:
            console_log += line

    if len(dispatcher_log) > 0:
        page.div(id="%d"%id_count, class_="dispatcher_log")
        page.pre()
        page.code(dispatcher_log)
        page.pre.close()
        page.div.close()

    if len(console_log) > 0:
        # console
        page.div(id="%d"%id_count, class_="console_log")
        page.pre()
        page.code(cgi.escape(console_log))
        page.pre.close()
        page.div.close()

    pp =  page.__str__()
    return pp

# for debugging
if __name__ == '__main__':
    file = open("/srv/lava/dev/var/www/lava-server/media/lava-logs/job-3020.log")
    print formatLogFileAsHtml(file)
