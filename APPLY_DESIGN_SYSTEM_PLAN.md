# 🎨 Plan to Apply Agora Design System to React Dashboards

## Current State
The React frontend dashboards (SME, QA, Team Leader) have basic custom CSS that doesn't match the deployed Flask app's Agora branding.

## Extracted Design System
✅ Successfully extracted complete design system from deployed app:
- Color palette (Agora Orange #F89D43, Navy #2D3847, etc.)
- Gradients (navy-to-lighter-navy for headers)
- Typography (system fonts, specific weights)
- Component styles (cards, buttons, tables, badges)
- Hover effects and transitions

See `DESIGN_SYSTEM_EXTRACTED.md` for full details.

## Implementation Plan

### Option 1: Global CSS File (RECOMMENDED)
Create a single `agora-theme.css` file that can be imported by all React components.

**Pros:**
- Centralized styling
- Easy to maintain
- Consistent across all dashboards
- CSS variables allow easy theming

**Cons:**
- Need to import in each component

### Option 2: Update Each Dashboard CSS
Update individual CSS files (SMEDashboard.css, QADashboard.css, TeamLeaderDashboard.css).

**Pros:**
- Isolated styling per component
- No additional imports needed

**Cons:**
- Code duplication
- Harder to maintain consistency
- Need to update multiple files

## Recommended Approach: Option 1

### Step 1: Create Global Theme File
**File**: `/home/user/webapp/DueDiligenceFrontend/src/styles/agora-theme.css`

Include:
- CSS variables (`:root` with all Agora colors)
- Base styles (body, containers)
- Component styles (cards, buttons, tables, badges)
- Utility classes (gradients, shadows)

### Step 2: Update React Components
Import the theme in each dashboard component:
```jsx
import '../styles/agora-theme.css';
```

### Step 3: Apply Agora Classes
Update JSX to use Agora-branded classes:
- Card headers with gradient backgrounds
- Orange primary buttons
- Navy-gradient table headers
- Proper badge colors
- Consistent spacing and shadows

### Step 4: Update Dashboard-Specific CSS
Keep dashboard-specific layout in individual CSS files, remove color/theme declarations.

## Key Changes to Apply

### KPI Cards
- **Header gradient**: `linear-gradient(135deg, #1a2332 0%, #2D3847 50%, #3d4d5f 100%)`
- **Border**: `1px solid #e5e7eb`
- **Border radius**: `8px`
- **Box shadow**: `0 1px 3px rgba(0, 0, 0, 0.1)`

### Charts
- **Primary color**: `#F89D43` (Agora Orange)
- **Secondary colors**: Navy palette for additional data series
- **Grid colors**: `#e5e7eb`

### Tables
- **Header gradient**: Navy gradient (same as cards)
- **Header text**: White, uppercase, letter-spacing
- **Row hover**: `rgba(248, 157, 67, 0.05)` (light orange tint)

### Buttons & Links
- **Primary**: Orange (#F89D43) with hover lift effect
- **Success**: Green (#10b981)
- **Warning**: Amber (#f59e0b)
- **Danger**: Red (#ef4444)

### Status Badges
- **Primary/Active**: Orange background
- **Info/Pending**: Navy background
- **Success**: Green background
- **Warning**: Amber background
- **Danger**: Red background

## Files to Create/Modify

### New Files:
1. `/home/user/webapp/DueDiligenceFrontend/src/styles/agora-theme.css`

### Modify:
1. `/home/user/webapp/DueDiligenceFrontend/src/components/SMEDashboard.jsx`
2. `/home/user/webapp/DueDiligenceFrontend/src/components/QADashboard.jsx`
3. `/home/user/webapp/DueDiligenceFrontend/src/components/TeamLeaderDashboard.jsx`
4. `/home/user/webapp/DueDiligenceFrontend/src/components/SMEDashboard.css` (simplify)
5. `/home/user/webapp/DueDiligenceFrontend/src/components/QADashboard.css` (simplify)
6. `/home/user/webapp/DueDiligenceFrontend/src/components/TeamLeaderDashboard.css` (simplify)

## Expected Result

After applying the design system:
- ✅ All dashboards will match the Flask app's Agora branding
- ✅ Consistent orange/navy color scheme throughout
- ✅ Professional gradients on cards and tables
- ✅ Proper hover effects and transitions
- ✅ Unified typography and spacing
- ✅ Easy to maintain and extend

## Next Steps

Would you like me to:
1. **Apply the design system now** (create theme file + update all dashboards)
2. **Show a preview** (apply to one dashboard first as a test)
3. **Customize the theme** (modify specific colors or styles before applying)

Let me know and I'll proceed!
