# 🎨 Design System Extracted from Deployed App

## Color Palette

### Primary Colors (Agora Branding)
```css
--agora-orange: #F89D43        /* Primary brand color */
--agora-navy: #2D3847          /* Secondary brand color */
--agora-navy-light: #3d4d5f    /* Lighter navy variant */
--agora-navy-lighter: #4d5d6f  /* Even lighter navy */
--agora-navy-dark: #1a2332     /* Dark navy for backgrounds */
--agora-white: #FFFFFF         /* White */
```

### Functional Colors
```css
--primary-color: #F89D43       /* Orange (same as agora-orange) */
--secondary-color: #e08932     /* Darker orange for hover states */
--accent-color: #10b981        /* Green for success */
--warning-color: #f59e0b       /* Amber for warnings */
--danger-color: #ef4444        /* Red for errors/danger */
```

### Background Colors
```css
--dark-bg: #1a2332             /* Dark background */
--light-bg: #f9fafb            /* Light background for page */
--border-color: #e5e7eb        /* Border color */
```

### Text Colors
```css
--text-primary: #111827        /* Primary text color */
--text-secondary: #6b7280      /* Secondary text color */
```

## Gradients

### Navbar & Header Gradient
```css
background: linear-gradient(135deg, #1a2332 0%, #2D3847 100%);
```

### Card Header Gradient
```css
background: linear-gradient(135deg, #1a2332 0%, #2D3847 50%, #3d4d5f 100%);
```

### Table Header Gradient
```css
background: linear-gradient(135deg, #1a2332 0%, #2D3847 50%, #3d4d5f 100%);
```

### Login Page Background Gradient
```css
background: linear-gradient(135deg, #1a2332 0%, #2D3847 50%, #3d4d5f 100%);
```

## Typography

### Font Family
```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
```

### Font Weights
- **600**: Headings, navbar brand, card headers
- **500**: Nav links, form labels, buttons, badges
- **Normal**: Body text

## Component Styling

### Cards
```css
border: 1px solid #e5e7eb;
border-radius: 8px;
box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
background-color: white;
margin-bottom: 1.5rem;
```

### Card Headers
```css
background: linear-gradient(135deg, #1a2332 0%, #2D3847 50%, #3d4d5f 100%);
color: white;
font-weight: 600;
border-radius: 8px 8px 0 0;
padding: 1rem 1.5rem;
```

### Buttons

#### Primary Button (Orange)
```css
background-color: #F89D43;
border-color: #F89D43;
color: white;
font-weight: 500;
transition: all 0.2s ease;
```

#### Primary Button Hover
```css
background-color: #e08932;
border-color: #e08932;
transform: translateY(-1px);
box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
```

#### Success Button
```css
background-color: #10b981;
border-color: #10b981;
```

#### Warning Button
```css
background-color: #f59e0b;
border-color: #f59e0b;
color: white;
```

#### Danger Button
```css
background-color: #ef4444;
border-color: #ef4444;
```

### Tables

#### Table Headers
```css
background: linear-gradient(135deg, #1a2332 0%, #2D3847 50%, #3d4d5f 100%);
color: white;
font-weight: 600;
border: none;
padding: 1rem;
text-transform: uppercase;
font-size: 0.85rem;
letter-spacing: 0.5px;
```

#### Table Row Hover
```css
background-color: rgba(248, 157, 67, 0.05); /* Light orange tint */
transition: background-color 0.2s ease;
```

### Badges

#### Primary Badge (Orange)
```css
background-color: #F89D43;
color: white;
font-weight: 500;
padding: 0.4rem 0.7rem;
border-radius: 6px;
```

#### Info Badge (Navy)
```css
background-color: #2D3847;
color: white;
```

### Alerts

#### Success Alert
```css
background-color: #d1fae5;
color: #065f46;
border: none;
border-radius: 8px;
```

#### Danger Alert
```css
background-color: #fee2e2;
color: #991b1b;
```

#### Info Alert
```css
background-color: #fff4e6;
color: #1a2332;
```

#### Warning Alert
```css
background-color: #fef3c7;
color: #92400e;
```

### Forms

#### Focus State
```css
border-color: #F89D43; /* Orange */
box-shadow: 0 0 0 0.2rem rgba(248, 157, 67, 0.25);
```

#### Labels
```css
font-weight: 500;
color: #111827;
margin-bottom: 0.5rem;
```

### Navbar

#### Navbar Background
```css
background: linear-gradient(135deg, #1a2332 0%, #2D3847 100%);
box-shadow: 0 2px 4px rgba(0,0,0,0.1);
```

#### Nav Links
```css
color: rgba(255, 255, 255, 0.85);
font-weight: 500;
padding: 0.5rem 1rem;
```

#### Nav Link Hover
```css
color: #F89D43; /* Orange */
background-color: rgba(248, 157, 67, 0.1);
border-radius: 6px;
```

#### Nav Link Active
```css
color: #F89D43;
background-color: rgba(248, 157, 67, 0.15);
border-radius: 6px;
```

### Footer

#### Footer Background
```css
background: linear-gradient(135deg, #1a2332 0%, #2D3847 100%);
box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
padding: 15px 0;
position: fixed;
bottom: 0;
```

#### Footer Text
```css
color: rgba(255, 255, 255, 0.7);
font-size: 0.9rem;
```

## Design Principles

1. **Consistent Gradients**: Navy-to-lighter-navy gradient used throughout (navbar, cards, tables)
2. **Orange Accent**: Primary action color (#F89D43) for buttons, links, highlights
3. **Subtle Shadows**: Light shadows for depth (0 1px 3px, 0 2px 4px)
4. **Rounded Corners**: 8px for cards, 6px for badges/buttons
5. **Smooth Transitions**: 0.2s ease transitions for hover effects
6. **Hover States**: Slight lift (translateY(-1px)) and shadow increase
7. **Typography**: System fonts for clean, modern look
8. **Spacing**: Consistent 1rem-1.5rem padding/margins

## Key Visual Elements

### Logo Placement
- **Navbar**: Scrutinise logo (60px height)
- **Footer**: Agora Consulting logo (50px height, right-aligned)

### Container Settings
```css
max-width: 1400px;
margin-top: 20px;
```

### Body Styling
```css
padding-top: 60px;  /* For fixed navbar */
padding-bottom: 80px; /* For fixed footer */
background-color: #f9fafb;
```

## CSS Variable Usage

All colors are defined as CSS variables in `:root` for easy theming:

```css
:root {
  --agora-orange: #F89D43;
  --agora-navy: #2D3847;
  --agora-navy-light: #3d4d5f;
  --agora-navy-lighter: #4d5d6f;
  --agora-navy-dark: #1a2332;
  --agora-white: #FFFFFF;
  
  --primary-color: var(--agora-orange);
  --secondary-color: #e08932;
  --accent-color: #10b981;
  --warning-color: #f59e0b;
  --danger-color: #ef4444;
  --dark-bg: var(--agora-navy-dark);
  --light-bg: #f9fafb;
  --border-color: #e5e7eb;
  --text-primary: #111827;
  --text-secondary: #6b7280;
}
```

This allows for easy color changes across the entire application.
