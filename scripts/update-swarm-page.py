#!/usr/bin/env python3
import sys
import json

filepath = sys.argv[1] if len(sys.argv) > 1 else '/Users/tommie/clawd/dashboard/swarm-monitor.html'

with open(filepath, 'r') as f:
    content = f.read()

# Add boat crew two section before </body>
boat_crew_section = '''
    <!-- BOAT CREW TWO ROSTER -->
    <div style="max-width: 1400px; margin: 2rem auto; padding: 0 2rem;">
        <div style="background: rgba(0,0,0,0.2); border-radius: 20px; padding: 2rem; margin-top: 2rem;">
            <h2 style="text-align: center; margin-bottom: 1.5rem; font-size: 1.8rem;">🚣 BOAT CREW TWO - Active Agents</h2>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;">
                <!-- Mac Mini -->
                <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 15px; border-left: 4px solid #48BB78;">
                    <h3 style="color: #48BB78; margin-bottom: 0.5rem;">🖥️ Mac Mini (100.88.105.106)</h3>
                    <p style="opacity: 0.8; margin-bottom: 1rem;">Orchestrator Hub</p>
                    <ul style="list-style: none; font-size: 0.9rem;">
                        <li>✓ Clawdbot Gateway</li>
                        <li>✓ Ollama qwen2.5:3b</li>
                        <li>✓ Dashboard Server (8080)</li>
                        <li>✓ LLM Gateway (5 models)</li>
                        <li>✓ PROJECT LEGION Hub</li>
                        <li>✓ Docker (n8n, redis, grafana)</li>
                    </ul>
                </div>
                
                <!-- Mac Pro -->
                <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 15px; border-left: 4px solid #9F7AEA;">
                    <h3 style="color: #9F7AEA; margin-bottom: 0.5rem;">💪 Mac Pro (100.89.75.126)</h3>
                    <p style="opacity: 0.8; margin-bottom: 1rem;">Code Bitch - Compute Node</p>
                    <ul style="list-style: none; font-size: 0.9rem;">
                        <li>✓ Fort Knox Storage (PRIMARY)</li>
                        <li>✓ Shared Brain Hub</li>
                        <li>✓ Ollama (larger models)</li>
                        <li>✓ Heavy compute tasks</li>
                        <li>✓ Code review</li>
                    </ul>
                </div>
                
                <!-- Dell -->
                <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 15px; border-left: 4px solid #F59E0B;">
                    <h3 style="color: #F59E0B; margin-bottom: 0.5rem;">💻 Dell (100.119.87.108)</h3>
                    <p style="opacity: 0.8; margin-bottom: 1rem;">Bottom Bitch - Production Apps</p>
                    <ul style="list-style: none; font-size: 0.9rem;">
                        <li>✓ TerminatorBot (paper trading)</li>
                        <li>✓ TaskBot (SaaS)</li>
                        <li>✓ Fraud Detection Platform</li>
                        <li>✓ Desktop control</li>
                        <li>✓ Browser automation</li>
                    </ul>
                </div>
                
                <!-- Google Cloud -->
                <div style="background: rgba(255,255,255,0.1); padding: 1.5rem; border-radius: 15px; border-left: 4px solid #3182CE;">
                    <h3 style="color: #3182CE; margin-bottom: 0.5rem;">☁️ Google Cloud (100.107.231.87)</h3>
                    <p style="opacity: 0.8; margin-bottom: 1rem;">LEGION Workers</p>
                    <ul style="list-style: none; font-size: 0.9rem;">
                        <li>✓ Pipeline Processor (2 instances)</li>
                        <li>✓ IT Operations Department</li>
                        <li>✓ 9 LEGION Agents</li>
                        <li>✓ Job hunting automation</li>
                    </ul>
                </div>
            </div>
            
            <div style="margin-top: 2rem; text-align: center;">
                <h3 style="margin-bottom: 1rem;">👥 Active Agents</h3>
                <div style="display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap;">
                    <span style="background: #48BB78; padding: 0.5rem 1rem; border-radius: 20px;">Main Agent (Clawd)</span>
                    <span style="background: #F59E0B; padding: 0.5rem 1rem; border-radius: 20px;">Bottom Bitch</span>
                    <span style="background: #9F7AEA; padding: 0.5rem 1rem; border-radius: 20px;">Code Bitch</span>
                    <span style="background: #3182CE; padding: 0.5rem 1rem; border-radius: 20px;">Mac Mini Agent</span>
                </div>
                <p style="margin-top: 1rem; opacity: 0.7; font-size: 0.9rem;">Total: 20 agents | 15 active services | 4 infrastructure nodes</p>
            </div>
        </div>
    </div>
'''

# Insert before </body>
if 'BOAT CREW TWO' not in content:
    content = content.replace('</body>', boat_crew_section + '\n</body>')
    with open(filepath, 'w') as f:
        f.write(content)
    print('Added Boat Crew Two roster to Swarm page!')
else:
    print('Boat Crew Two section already exists')
