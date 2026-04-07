#!/usr/bin/env python3
import sys

filepath = sys.argv[1] if len(sys.argv) > 1 else '/Users/tommie/clawd/dashboard/fort-knox.html'

with open(filepath, 'r') as f:
    content = f.read()

# Add info section before </body>
info_section = '''
    <!-- FORT KNOX INFO SECTION -->
    <div style="max-width: 1400px; margin: 2rem auto; padding: 0 2rem;">
        <div style="background: rgba(0,0,0,0.2); border-radius: 20px; padding: 2rem;">
            <h2 style="text-align: center; margin-bottom: 1.5rem; font-size: 1.5rem;">📋 Backup Policy Details</h2>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.5rem;">
                <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 15px;">
                    <h3 style="color: #FFD700; margin-bottom: 1rem;">🏦 Primary Vault</h3>
                    <ul style="list-style: none; font-size: 0.9rem;">
                        <li>📍 Location: Mac Pro (100.89.75.126)</li>
                        <li>📦 Storage: ~/fort-knox-backups/</li>
                        <li>🔄 Retention: 30 versions</li>
                        <li>⏰ Schedule: Before each deploy</li>
                    </ul>
                </div>
                
                <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 15px;">
                    <h3 style="color: #48BB78; margin-bottom: 1rem;">✅ Protected Items</h3>
                    <ul style="list-style: none; font-size: 0.9rem;">
                        <li>✓ ~/clawd/ (configs, scripts, memory)</li>
                        <li>✓ ~/.clawdbot/ (agent configs)</li>
                        <li>✓ ~/shared-memory/ (cross-agent data)</li>
                        <li>✓ Dashboard pages</li>
                    </ul>
                </div>
                
                <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 15px;">
                    <h3 style="color: #E53E3E; margin-bottom: 1rem;">⚠️ Critical Rules</h3>
                    <ul style="list-style: none; font-size: 0.9rem;">
                        <li>❌ NEVER reduce MAX_VERSIONS below 30</li>
                        <li>❌ NEVER auto-delete without validation</li>
                        <li>✓ Run backup-before-truncate.sh first</li>
                        <li>✓ Check backups exist before deletions</li>
                    </ul>
                </div>
            </div>
            
            <div style="margin-top: 2rem; padding: 1.5rem; background: #1A202C; border-radius: 10px;">
                <h3 style="color: #48BB78; margin-bottom: 1rem;">💻 Quick Commands</h3>
                <code style="display: block; color: #E2E8F0; font-size: 0.85rem; line-height: 1.8;">
                    # Check backup count<br>
                    ls -la ~/clawd-versions/ | wc -l<br><br>
                    # Backup before truncate<br>
                    ~/clawd/scripts/backup-before-truncate.sh<br><br>
                    # Restore from version<br>
                    rsync -av ~/clawd-versions/vYYYYMMDD-HHMMSS/ ~/clawd/
                </code>
            </div>
            
            <div style="text-align: center; margin-top: 1.5rem; opacity: 0.7;">
                <p>📚 Full documentation: ~/shared-memory/FORT_KNOX_BACKUP_POLICY.md</p>
                <p>Last updated: March 7, 2026 | MAX_VERSIONS: 30</p>
            </div>
        </div>
    </div>
'''

# Insert before </body>
if 'FORT KNOX INFO SECTION' not in content:
    content = content.replace('</body>', info_section + '\n</body>')
    with open(filepath, 'w') as f:
        f.write(content)
    print('Added info section to Fort Knox page!')
else:
    print('Info section already exists')
