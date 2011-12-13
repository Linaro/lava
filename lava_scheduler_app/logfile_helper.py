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
        return ('', "Log file is missing")

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

    sections = []
    cur_section_type = None
    cur_section = []

    for line in logfile:
        print repr(line)
        line = line.replace('\r', '')
        if not line:
            continue
        if line == 'Traceback (most recent call last):\n':
            sections.append((cur_section_type, len(cur_section), cur_section))
            cur_section_type = 'traceback'
            cur_section = [line]
        elif cur_section_type == 'traceback':
            cur_section.append(line)
            if not line.startswith(' '):
                sections.append((cur_section_type, len(cur_section), cur_section))
                cur_section_type = None
                cur_section = []
                continue
        elif line.find("<LAVA_DISPATCHER>") != -1 or \
           line.find("lava_dispatcher") != -1 or \
           line.find("CriticalError:") != -1 :
            if cur_section_type is None:
                cur_section_type = 'console'
            elif cur_section_type == 'log':
                sections.append((cur_section_type, len(cur_section), cur_section))
                cur_section_type = 'console'
                cur_section = []
            cur_section.append(line)
        else:
            if cur_section_type is None:
                cur_section_type = 'log'
            elif cur_section_type == 'console':
                sections.append((cur_section_type, len(cur_section), cur_section))
                cur_section_type = 'log'
                cur_section = []
            cur_section.append(line)
    if cur_section:
        sections.append((cur_section_type, len(cur_section), cur_section))

    return sections


# for debugging
if __name__ == '__main__':
    file = open("/srv/lava/dev/var/www/lava-server/media/lava-logs/job-3020.log")
    print formatLogFileAsHtml(file)
