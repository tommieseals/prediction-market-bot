#!/usr/bin/env python3
import re

path = '/Users/tommie/clawd/VisionClaw/samples/CameraAccess/CameraAccess.xcodeproj/project.pbxproj'

with open(path, 'r') as f:
    content = f.read()

content = re.sub(r'DEVELOPMENT_TEAM = WY253UX7FC', 'DEVELOPMENT_TEAM = ', content)

with open(path, 'w') as f:
    f.write(content)

print('Fixed DEVELOPMENT_TEAM')
