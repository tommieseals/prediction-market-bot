#!/usr/bin/env python3
"""Fix Xcode project for VisionClaw - careful line-by-line edits"""

path = '/Users/tommie/clawd/VisionClaw/samples/CameraAccess/CameraAccess.xcodeproj/project.pbxproj'

with open(path, 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    # Change bundle ID
    if 'com.xiaoanliu.VisionClaw' in line:
        line = line.replace('com.xiaoanliu.VisionClaw', 'com.rusty.VisionClaw')
    
    # Clear development team (keep the line structure)
    if 'DEVELOPMENT_TEAM = WY253UX7FC' in line:
        line = line.replace('DEVELOPMENT_TEAM = WY253UX7FC', 'DEVELOPMENT_TEAM = ""')
    
    new_lines.append(line)

with open(path, 'w') as f:
    f.writelines(new_lines)

print('Fixed successfully')
