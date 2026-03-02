# How to View the Permission Marketing MCP Diagram

This document provides step-by-step instructions for viewing the comprehensive PlantUML diagram.

## 📊 Diagram Contents

The `permission-marketing-mcp-system.puml` file contains **4 pages**:

### Page 1: Architecture & Permission Ladder
- MCP Server components (Tools, Resources, Prompts)
- Seth Godin's 5-level permission ladder mapped to technical scopes
- Color-coded levels (green → red for situational → agentic)
- Integration points (Agent, Database, Audit Log)

### Page 2: Permission Escalation Flow
- Complete sequence diagram showing user journey
- From first visit to autonomous delegation
- 6 interaction boxes showing progressive permission requests
- Real conversational examples at each level

### Page 3: Permission Resource Schema
- JSON data model for permission grants
- Example permission objects (P123, P456, P789)
- Constraints and guardrails structure
- Audit trail schema

### Page 4: Key Insights
- Visual comparison: Interruption → Permission → Agentic
- Summary of new capabilities
- Core principles

## 🖥️ Method 1: VS Code with PlantUML Extension (BEST)

### Step 1: Install Extension
1. Open VS Code
2. Press `Cmd+Shift+X` (Mac) or `Ctrl+Shift+X` (Windows/Linux)
3. Search for **"PlantUML"**
4. Install the extension by **jebbs**
5. You may also need to install **Graphviz**:
   ```bash
   # macOS
   brew install graphviz
   
   # Ubuntu/Debian
   sudo apt-get install graphviz
   
   # Windows (with Chocolatey)
   choco install graphviz
   ```

### Step 2: View the Diagram
1. Open `permission-marketing-mcp-system.puml` in VS Code
2. Press **`Alt+D`** (Windows/Linux) or **`Option+D`** (Mac)
3. A preview pane will appear showing the rendered diagram
4. Use page controls to navigate through all 4 pages

### Step 3: Export (Optional)
Right-click in the preview → **"Export Current Diagram"** → Choose format:
- PNG (for presentations)
- SVG (for high-quality, zoomable images)
- PDF (for sharing)

## 🌐 Method 2: Online PlantUML Server (NO INSTALL)

### Quick & Easy Online Viewing

1. Go to: **http://www.plantuml.com/plantuml/uml/**

2. Copy **ALL** contents from `permission-marketing-mcp-system.puml`
   - In VS Code: `Cmd+A` / `Ctrl+A` → `Cmd+C` / `Ctrl+C`

3. Paste into the web editor

4. View rendered diagram instantly

5. Navigate pages using the page selector (top-right)

6. Export options:
   - PNG image
   - SVG vector
   - ASCII art (text-based)
   - Direct URL to share

### Alternative Online Viewers
- **PlantText:** https://www.planttext.com/
- **LiveUML:** http://liveuml.com/
- **PlantUML QEditor:** https://github.com/borisbat/plantuml-qeditor

## 🖼️ Method 3: Command Line (For Developers)

### Install PlantUML

#### macOS
```bash
brew install plantuml
```

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install plantuml
```

#### Windows
Download from: https://plantuml.com/download

Or with Chocolatey:
```bash
choco install plantuml
```

### Generate Images

```bash
# Navigate to project directory
cd /Users/backelite/Documents/MPCServer2

# Generate PNG (all pages)
plantuml permission-marketing-mcp-system.puml

# Generate SVG (better quality, zoomable)
plantuml -tsvg permission-marketing-mcp-system.puml

# Generate PDF
plantuml -tpdf permission-marketing-mcp-system.puml

# Output files created:
# - permission-marketing-mcp-system.png (or .svg, .pdf)
# - permission-marketing-mcp-system_001.png (page 2)
# - permission-marketing-mcp-system_002.png (page 3)
# - permission-marketing-mcp-system_003.png (page 4)
```

### View Generated Images
```bash
# macOS
open permission-marketing-mcp-system.png

# Linux
xdg-open permission-marketing-mcp-system.png

# Windows
start permission-marketing-mcp-system.png
```

## 📱 Method 4: Mobile/Tablet Viewing

### Option A: PlantUML Viewer Apps
- **Android:** PlantUML Viewer (Google Play)
- **iOS:** Use Safari/Chrome → Online PlantUML server

### Option B: GitHub Rendering
1. Push code to GitHub repository
2. GitHub automatically renders `.puml` files
3. View on any device with a browser

## 🎨 Diagram Navigation Tips

### Understanding the Color Scheme
- **Green (#90EE90):** Level 1 - Situational (auto-granted)
- **Light Yellow (#FFFFE0):** Level 2 - Brand Trust (opt-in)
- **Gold (#FFD700):** Level 3 - Personal Relationship (authenticated)
- **Orange (#FFA500):** Level 4 - Points Permission (loyalty)
- **Red (#FF6B6B):** Level 5 - Agentic (delegation + constraints)

### Key Sections to Focus On

1. **Permission Ladder (Page 1, Right Side)**
   - Shows Seth Godin's original ladder
   - Maps each level to technical scopes
   - Explains what changes at each level

2. **Escalation Flow (Page 2)**
   - Real conversational examples
   - Shows HOW permissions are requested
   - Demonstrates constraint negotiation

3. **Data Model (Page 3)**
   - Technical implementation details
   - JSON structure for storage
   - Guardrails for Level 5

4. **Insights (Page 4)**
   - Historical context (interruption → permission → agentic)
   - Summary of capabilities
   - Core principles

## 🔍 Troubleshooting

### Diagram won't render in VS Code
**Problem:** Preview shows "Error rendering diagram"

**Solutions:**
1. Check Java installation: `java -version`
   - PlantUML requires Java Runtime
   - Install from: https://java.com/download
2. Check Graphviz: `dot -V`
   - Required for complex diagrams
   - Install as shown in Method 1
3. Restart VS Code after installing dependencies
4. Check PlantUML extension logs: `View → Output → PlantUML`

### Online viewer times out
**Problem:** Large diagram takes too long

**Solutions:**
1. Try different online service (PlantText, LiveUML)
2. Use command-line generation instead
3. Split into smaller sections if needed

### Generated images are low quality
**Problem:** PNG output is blurry

**Solutions:**
1. Use SVG instead: `plantuml -tsvg <file>`
   - Vector graphics scale perfectly
   - Better for presentations
2. Increase DPI for PNG:
   ```bash
   plantuml -Sdpi=300 permission-marketing-mcp-system.puml
   ```
3. Use PDF for print: `plantuml -tpdf`

### Can't find generated files
**Problem:** After running plantuml, no output

**Solutions:**
1. Check current directory: `ls -la *.png`
2. Specify output path:
   ```bash
   plantuml -o /path/to/output permission-marketing-mcp-system.puml
   ```
3. Check for error messages in terminal

## 🎓 Next Steps After Viewing

1. **Understand the Architecture** (Page 1)
   - Study how MCP tools expose permission operations
   - Review the permission ladder configuration
   - See how resources provide state access

2. **Trace the User Journey** (Page 2)
   - Follow a user from first visit to delegation
   - Note how value is exchanged at each level
   - See constraint negotiation in action

3. **Examine the Data Model** (Page 3)
   - Understand permission grant structure
   - Review constraint/guardrail requirements
   - Study the audit trail format

4. **Run the Python Demo**
   - See the concepts in action
   - Modify constraints and observe behavior
   - Experiment with different permission flows

5. **Read the Full Documentation**
   - [README.md](README.md) for comprehensive guide
   - [QUICKSTART.md](QUICKSTART.md) for hands-on tutorial
   - Original article by Jérôme Coignard

## 💡 Pro Tips

### For Presentations
1. Export to SVG for crisp projector display
2. Use page 2 (flow) as main visual
3. Print page 3 (data model) as handout

### For Development
1. Keep diagram open while coding
2. Reference permission levels in code comments
3. Use audit schema for compliance discussions

### For Learning
1. Start with page 4 (insights) for context
2. Study page 1 (ladder) to understand levels
3. Walk through page 2 (flow) step by step
4. Deep dive into page 3 (schema) for implementation

---

## ✅ Verification Checklist

After viewing, you should understand:
- [ ] Seth Godin's 5 permission levels
- [ ] How each level maps to technical scopes
- [ ] Why Level 5 requires constraints
- [ ] How permission requests work conversationally
- [ ] The data structure for permission grants
- [ ] Why audit trails matter (GDPR compliance)
- [ ] How revocation enables graceful degradation

---

**Need help?** Check [QUICKSTART.md](QUICKSTART.md) or [README.md](README.md) for more details.
