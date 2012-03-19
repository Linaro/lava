import re

def getDispatcherErrors(logfile):
    errors = ""
    for line in logfile:
        if line.find("CriticalError:") != -1 or \
           line.find("Lava failed on test:") != -1 :
            errors += line

    return errors

def getDispatcherLogMessages(logfile):
    logs = []
    log_prefix = '<LAVA_DISPATCHER>'
    action_begin = '[ACTION-B]'
    level_pattern = re.compile('....-..-.. (..:..:.. .. ([A-Z]+): .*)')
    for line in logfile:
        # log_prefix not always start at beginning of the line
        pos = line.find(log_prefix)
        if (pos == -1): # log_prefix not found
            continue
        if (pos > 0): # remove log_prefix leading characters
            line = line[pos:-1]

        line = line[len(log_prefix):].strip()
        match = level_pattern.match(line)
        if not match:
            continue
        line = match.group(1)
        if len(line) > 120:
            line = line[:120] + '...'
        if line.find(action_begin) != -1:
            logs.append((match.group(2), line, "action"))
        else:
            logs.append((match.group(2), line, ""))
    return logs

class Sections:
    def __init__(self):
        self.sections = []
        self.cur_section_type = None
        self.cur_section = []
    def push(self, type, line):
        if type != self.cur_section_type:
            self.close()
            self.cur_section_type = type
        self.cur_section.append(line)
    def close(self):
        if self.cur_section_type is not None:
            self.sections.append(
                (self.cur_section_type,
                 len(self.cur_section),
                 ''.join(self.cur_section)))
        self.cur_section_type = None
        self.cur_section = []

def formatLogFile(logfile):
    if not logfile:
        return [('log', 1, "Log file is missing")]

    sections = Sections()

    for line in logfile:
        line = line.replace('\r', '')
        line = unicode(line, 'ascii', 'replace')
        if not line:
            continue
        if line == 'Traceback (most recent call last):\n':
            sections.push('traceback', line)
        elif sections.cur_section_type == 'traceback':
            sections.push('traceback', line)
            if not line.startswith(' '):
                sections.close()
            continue
        elif line.find("<LAVA_DISPATCHER>") != -1 or \
                 line.find("lava_dispatcher") != -1 or \
                 line.find("CriticalError:") != -1 :
            sections.push('log', line)
        else:
            sections.push('console', line)
    sections.close()

    return sections.sections
