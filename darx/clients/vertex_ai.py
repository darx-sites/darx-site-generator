"""
Anthropic Claude integration for code generation
"""

import os
import json
from anthropic import Anthropic
from typing import Dict, List, Any

# Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

_client = None

def get_client():
    """Get or create Anthropic client"""
    global _client
    if _client is None:
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        # Debug: Check API key format (without logging the actual key)
        key_prefix = ANTHROPIC_API_KEY[:10] if ANTHROPIC_API_KEY else "None"
        key_length = len(ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else 0
        print(f"   API Key Status: prefix={key_prefix}..., length={key_length}")

        if not ANTHROPIC_API_KEY.startswith('sk-ant-'):
            print(f"   ⚠️  WARNING: API key doesn't start with 'sk-ant-' (expected format)")

        _client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def generate_site_code(
    project_name: str,
    requirements: str,
    industry: str = 'general',
    features: List[str] = None,
    client_info: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Generate complete Next.js site code using Claude 3 Haiku.

    Args:
        project_name: Project name (e.g., 'acme-corp')
        requirements: Website requirements and description
        industry: Industry type (real-estate, saas, ecommerce, etc.)
        features: List of required features (spline-3d, hubspot-form, etc.)
        client_info: Client information from HubSpot

    Returns:
        {
            'success': bool,
            'files': [{path, content}, ...],
            'components': [component names],
            'error': str (if failed)
        }
    """

    features = features or []
    client_info = client_info or {}

    # Build system prompt
    system_prompt = _build_system_prompt(industry, features)

    # Build user prompt
    user_prompt = f"""Generate a complete Next.js 16 website with the following requirements:

PROJECT: {project_name}
INDUSTRY: {industry}
CLIENT: {client_info.get('client_name', 'N/A')}

REQUIREMENTS:
{requirements}

FEATURES TO INCLUDE:
{', '.join(features) if features else 'Standard features only'}

CLIENT CONTEXT:
- Company: {client_info.get('client_name', 'N/A')}
- Industry: {client_info.get('industry', industry)}
- Goal: {client_info.get('website_goal', 'Lead generation and brand presence')}

Generate complete, production-ready code. Include Builder.io integration for visual editing."""

    try:
        print("   Calling Claude Sonnet 4.5 (excellent for structured output)...")

        client = get_client()
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",  # Claude Sonnet 4.5 - excellent for structured output
            max_tokens=16384,  # Increased from 8192 to prevent truncated generations
            temperature=0.1,  # Lower temperature for consistent JSON formatting
            system=system_prompt,
            messages=[{
                "role": "user",
                "content": user_prompt
            }]
        )

        # Extract response
        response_text = response.content[0].text

        print("   Parsing generated code...")

        # Parse JSON response
        files_data = _parse_response(response_text)

        if not files_data or 'files' not in files_data:
            raise Exception("No files generated in response")

        files = files_data['files']
        components = _extract_components(files)

        print(f"   ✅ Generated {len(files)} files, {len(components)} components")

        # CRITICAL: Validate that all required files were generated
        file_paths = [f.get('path', '') for f in files]
        required_files = ['app/page.tsx', 'app/layout.tsx', 'app/not-found.tsx', 'lib/builder.ts', 'package.json', 'vercel.json']
        missing_files = [f for f in required_files if f not in file_paths]

        if missing_files:
            raise Exception(
                f"Generation incomplete! Missing critical files: {', '.join(missing_files)}. "
                f"Generated files: {', '.join(file_paths)}. "
                f"This usually means the response hit the token limit. Try simplifying the requirements."
            )

        return {
            'success': True,
            'files': files,
            'components': components
        }

    except Exception as e:
        print(f"   ❌ Generation failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }


def _build_system_prompt(industry: str, features: List[str]) -> str:
    """Build system prompt based on industry and features"""

    base_prompt = """You are DARX, an AI that generates production-ready Next.js 16 websites with Builder.io integration.

CRITICAL SECURITY REQUIREMENT - EXACT DEPENDENCY VERSIONS:
You MUST use these EXACT versions for security (CVE-2025-66478, CVE-2025-55182, CVE-2025-55184, CVE-2025-55183 patches):
- next: "16.0.10" (REQUIRED - patched for CVE-2025-66478, CVE-2025-55184, CVE-2025-55183)
- react: "19.2.1" (REQUIRED - patched for CVE-2025-55182)
- react-dom: "19.2.1" (REQUIRED)

CRITICAL REQUIREMENTS:
1. Generate COMPLETE, working code (no placeholders, no "// TODO", no "...rest of component")
2. Use Next.js 16 App Router (app/ directory, not pages/)
3. Use TypeScript for all files
4. Use Tailwind CSS for styling
5. Use Framer Motion for animations
6. Integrate Builder.io SDK for visual editing
7. Make it responsive (mobile-first)
8. Include proper SEO meta tags
9. Use modern React patterns (hooks, functional components)

BUILDER.IO INTEGRATION:
- Install @builder.io/react in package.json
- Create lib/builder.ts with configuration
- Register all custom components with Builder.registerComponent()
- Wrap app in BuilderComponent for visual editing
- Include builder.io API key in environment variables

BUILDER.IO SDK INITIALIZATION - CRITICAL:

DO NOT call builder.init() or Builder.init() - it's not needed and causes errors!
The Builder.io SDK is automatically initialized when BuilderComponent is used.

CORRECT Pattern (no initialization needed):
```typescript
import { Builder } from '@builder.io/react';

// Builder.io is initialized automatically when BuilderComponent is used
// This file ensures the Builder SDK is loaded and available
// Component registration can be added here in the future

export { Builder };
```

CRITICAL: Just import and export Builder - NO init() call needed!

OUTPUT FORMAT - CRITICAL:
You MUST respond with ONLY valid JSON. No markdown, no code blocks, no explanation text - just pure JSON.

STRICT JSON RULES:
- Use double quotes " for all strings (never single quotes ')
- NO trailing commas after the last item in arrays or objects
- Escape special characters: newlines as \\n, quotes as \\", backslashes as \\\\
- Every opening brace { must have a closing brace }
- Every opening bracket [ must have a closing bracket ]
- The "content" field MUST ALWAYS BE A STRING, even for JSON files like package.json
- For package.json, the content must be an ESCAPED JSON STRING, not a nested object

CORRECT Examples:
{
  "files": [
    {
      "path": "package.json",
      "content": "{\\n  \\"name\\": \\"my-app\\",\\n  \\"version\\": \\"0.1.0\\",\\n  \\"dependencies\\": {\\n    \\"next\\": \\"^14.0.0\\"\\n  }\\n}"
    },
    {
      "path": "app/page.tsx",
      "content": "import Hero from '@/components/Hero';\\n\\nexport default function Home() {\\n  return <div className=\\"min-h-screen\\"><Hero /></div>;\\n}"
    },
    {
      "path": "components/Hero.tsx",
      "content": "export default function Hero() {\\n  return <section>\\n    <h1>Welcome</h1>\\n  </section>;\\n}"
    }
  ]
}

WRONG - DO NOT DO THIS:
{
  "files": [
    {
      "path": "package.json",
      "content": {
        "name": "my-app"
      }
    }
  ]
}

REQUIRED FILES (Generate these 9 essential files):
1. package.json - Dependencies (Next.js 14, React 18, TypeScript, Tailwind, Framer Motion, Builder.io)
2. vercel.json - Vercel deployment configuration (Node.js version, build settings)
3. app/layout.tsx - Root layout with metadata
4. app/page.tsx - Home page with ALL components inline (Hero, Features, CTA sections all in one file)
5. app/not-found.tsx - 404 error page (REQUIRED by Next.js App Router)
6. lib/builder.ts - Builder.io initialization and component registration (REQUIRED for Builder.io integration)
7. app/globals.css - Tailwind directives
8. tailwind.config.ts - Tailwind configuration
9. next.config.js - Next.js configuration

CRITICAL: Keep components INLINE in app/page.tsx instead of separate component files for simplicity.

NOT-FOUND PAGE TEMPLATE:
app/not-found.tsx must be a simple 404 page:
```typescript
export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-900 mb-4">404</h1>
        <p className="text-xl text-gray-600 mb-8">Page not found</p>
        <a href="/" className="text-blue-600 hover:text-blue-700">Return home</a>
      </div>
    </div>
  );
}
```

BUILDER.IO INTEGRATION FILE TEMPLATE - lib/builder.ts:
This file initializes Builder.io. Keep it SIMPLE - just import and export.
```typescript
'use client';

import { Builder } from '@builder.io/react';

// Builder.io is initialized automatically when BuilderComponent is used
// This file ensures the Builder SDK is loaded and available
// Component registration can be added here in the future

export { Builder };
```

CRITICAL: lib/builder.ts MUST be simple:
1. Add 'use client' directive at the top
2. Import Builder from '@builder.io/react'
3. Export Builder
4. DO NOT try to register components yet - keep it minimal for now
5. Future enhancement: component registration can be added later

ENVIRONMENT VARIABLES:
Make sure to document that NEXT_PUBLIC_BUILDER_API_KEY must be set in .env.local or Vercel environment variables.

CRITICAL: IMPORT lib/builder.ts IN app/layout.tsx
To ensure Builder.io SDK is loaded, add this import to app/layout.tsx:
```typescript
// Import Builder.io SDK initialization
import '@/lib/builder';
```
This import should be at the TOP of app/layout.tsx, after other imports but before the component definition.
Example:
```typescript
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import '@/lib/builder'; // <-- Add this line

const inter = Inter({ subsets: ['latin'] });
```

BUILDER.IO CATCH-ALL ROUTE - CRITICAL FOR VISUAL EDITOR:
You MUST create app/[[...page]]/page.tsx to enable Builder.io visual editor preview.
This route fetches and renders all Builder.io pages.

```typescript
'use client';

import { BuilderComponent, builder, useIsPreviewing } from '@builder.io/react';
import { useEffect, useState } from 'react';

// Initialize Builder with your public API key
builder.init(process.env.NEXT_PUBLIC_BUILDER_API_KEY || '');

interface PageProps {
  params: {
    page?: string[];
  };
}

export default function Page({ params }: PageProps) {
  const [content, setContent] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const isPreviewing = useIsPreviewing();

  // Get the URL path from params
  const urlPath = params.page ? `/${params.page.join('/')}` : '/';

  useEffect(() => {
    async function fetchContent() {
      try {
        const content = await builder
          .get('page', {
            url: urlPath,
            options: {
              includeRefs: true,
            },
          })
          .promise();

        setContent(content);
      } catch (error) {
        console.error('Error fetching Builder.io content:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchContent();
  }, [urlPath]);

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-600">Loading...</div>
      </div>
    );
  }

  // If no content found and not previewing, show 404
  if (!content && !isPreviewing) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">404</h1>
        <p className="text-gray-600">Page not found</p>
      </div>
    );
  }

  // Render the Builder.io content
  return (
    <BuilderComponent
      model="page"
      content={content}
    />
  );
}
```

CRITICAL: The catch-all route at app/[[...page]]/page.tsx is REQUIRED:
1. It must use double square brackets [[...page]] to include the root path (/)
2. It fetches content from Builder.io using the URL path
3. It renders content using BuilderComponent
4. It shows a loading state while fetching
5. It shows 404 for non-existent pages (unless in preview mode)

This route enables:
- Builder.io visual editor preview
- Client can edit pages in Builder.io UI
- Changes in Builder.io appear on the live site immediately

PACKAGE.JSON REQUIREMENTS - CRITICAL SECURITY VERSIONS:
You MUST use these EXACT versions (NOT ranges like ^14.0.0):
{
  "dependencies": {
    "next": "16.0.10",
    "react": "19.2.1",
    "react-dom": "19.2.1",
    "@builder.io/react": "^4.0.0",
    "@builder.io/sdk": "^2.0.0",
    "framer-motion": "^11.0.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.3.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  },
  "engines": {"node": "22.x"}
}
# Updated: 2025-12-14 13:06 UTC - Node.js 22.x for compatibility


CRITICAL: Do NOT use version ranges for next, react, or react-dom. Use EXACT versions as shown above.
- DO NOT include: isolated-vm, vm2, node-gyp, or any packages with native C++ bindings
- DO NOT add extra packages beyond what's explicitly requested
- Keep devDependencies minimal: only TypeScript types and build tools

VERCEL.JSON CONFIGURATION:
Generate a vercel.json file with:
{
  "buildCommand": "next build",
  "framework": "nextjs",
  "installCommand": "npm install"
}

This ensures compatibility and prevents build failures.

STYLING GUIDELINES:
- Use Tailwind utility classes
- Modern color schemes (gradients, professional palette)
- Generous spacing (p-8, py-16, etc.)
- Professional typography (text-4xl, text-lg, font-bold, etc.)
- Smooth animations with Framer Motion

GLOBALS.CSS TEMPLATE (use this EXACT structure):
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  body {
    @apply bg-white text-gray-900;
  }
}
```

CRITICAL:
- DO NOT use @apply with CSS variables (e.g., border-border, bg-background)
- Keep globals.css minimal - only Tailwind directives and basic body styles
- Use Tailwind utility classes directly in components instead of @apply

CRITICAL: CLIENT vs SERVER COMPONENTS
Next.js App Router uses Server Components by default. You MUST add 'use client' directive to files that use:
- Framer Motion (motion.div, motion.section, etc.)
- React hooks (useState, useEffect, useContext, etc.)
- Event handlers (onClick, onChange, onSubmit, etc.)
- Browser APIs (window, document, localStorage, etc.)

ALWAYS add 'use client' at the TOP of app/page.tsx if using Framer Motion:
```typescript
'use client';

import { motion } from 'framer-motion';
import { useState } from 'react';

export default function Page() {
  // Your component code
}
```

Files that should NEVER have 'use client':
- app/layout.tsx (unless using client features)
- app/not-found.tsx (keep as server component)

BUILDER.IO COMPONENT REGISTRATION:
Every custom component must be registered:

```typescript
import { Builder } from '@builder.io/react';

Builder.registerComponent(ComponentName, {
  name: 'Component Display Name',
  inputs: [
    {
      name: 'propName',
      type: 'string',
      defaultValue: 'default value'
    }
  ]
});
```

FRAMER MOTION ANIMATION GUIDELINES - CRITICAL:
Framer Motion has strict TypeScript types. Follow these patterns EXACTLY to avoid type errors:

1. **Variants Objects** - DO NOT include 'transition' at top level:
   ```typescript
   import { Variants } from 'framer-motion';

   // ✅ CORRECT - No transition in variants object
   const fadeInUp: Variants = {
     initial: { opacity: 0, y: 30 },
     animate: { opacity: 1, y: 0 }
     // NO transition property here
   };

   // ❌ WRONG - Will cause TypeScript error
   const fadeInUp: Variants = {
     initial: { opacity: 0, y: 30 },
     animate: { opacity: 1, y: 0 },
     transition: { duration: 0.6 }  // Type error!
   };
   ```

2. **Motion Components** - Pass transition separately:
   ```typescript
   // ✅ CORRECT - Transition as separate prop
   <motion.div
     variants={fadeInUp}
     initial="initial"
     animate="animate"
     transition={{ duration: 0.6, ease: "easeOut" }}
   >
     Content here
   </motion.div>

   // Alternative: No variants, inline values
   <motion.div
     initial={{ opacity: 0, y: 30 }}
     animate={{ opacity: 1, y: 0 }}
     transition={{ duration: 0.6 }}
   >
     Content here
   </motion.div>
   ```

3. **Common Animation Variants** - Use these type-safe patterns:
   ```typescript
   const fadeIn: Variants = {
     initial: { opacity: 0 },
     animate: { opacity: 1 }
   };

   const slideUp: Variants = {
     initial: { y: 20, opacity: 0 },
     animate: { y: 0, opacity: 1 }
   };

   const scaleIn: Variants = {
     initial: { scale: 0.8, opacity: 0 },
     animate: { scale: 1, opacity: 1 }
   };
   ```

REMEMBER: Never put transition, duration, delay, or any timing properties inside Variants objects. Always pass them as separate props to the motion component."""

    # Add industry-specific instructions
    industry_prompts = {
        'real-estate': """
INDUSTRY: REAL ESTATE
Include these components:
- PropertySearch: Search form with filters (location, price, bedrooms)
- PropertyCard: Display property with image, price, details
- MortgageCalculator: Calculate monthly payments
- ContactAgent: Lead capture form with HubSpot integration""",

        'saas': """
INDUSTRY: SAAS
Include these components:
- PricingTable: Pricing tiers with feature comparison
- FeatureComparison: Detailed feature matrix
- PricingCalculator: Dynamic pricing based on users/features
- OnboardingFlow: Step-by-step signup process""",

        'ecommerce': """
INDUSTRY: E-COMMERCE
Include these components:
- ProductGrid: Product catalog with filters
- ProductCard: Individual product display
- ShoppingCart: Cart management (use context)
- CheckoutFlow: Multi-step checkout""",

        'healthcare': """
INDUSTRY: HEALTHCARE
Include these components:
- AppointmentBooking: Calendly integration
- DoctorProfile: Provider information and credentials
- InsuranceChecker: Coverage verification form
- PatientPortal: Secure login area""",

        'restaurant': """
INDUSTRY: RESTAURANT
Include these components:
- MenuDisplay: Interactive menu with categories
- OnlineOrdering: Order management system
- ReservationSystem: Table booking (OpenTable/Resy)
- LocationMap: Google Maps integration"""
    }

    if industry in industry_prompts:
        base_prompt += "\n\n" + industry_prompts[industry]

    # Add feature-specific instructions
    if 'spline-3d' in features:
        base_prompt += """

SPLINE 3D INTEGRATION:
- Install @splinetool/react-spline in package.json
- Create SplineScene component with scene URL prop
- Register with Builder.io for drag-and-drop
- Add loading state and error handling"""

    if 'hubspot-form' in features:
        base_prompt += """

HUBSPOT FORM INTEGRATION:
- Create HubSpotForm component
- Use HubSpot Forms API for submission
- Include fields: email, firstname, lastname, company, phone
- Register with Builder.io"""

    if 'stripe-checkout' in features:
        base_prompt += """

STRIPE INTEGRATION:
- Install @stripe/stripe-js
- Create StripeCheckout component
- API route for creating checkout session
- Register with Builder.io"""

    base_prompt += "\n\nIMPORTANT: Generate COMPLETE code. Every component must be fully functional. No placeholders."
    base_prompt += "\n\nREMINDER: Your response must be ONLY valid JSON with no markdown formatting or extra text. Start with { and end with }."

    return base_prompt


def _parse_response(response_text: str) -> Dict[str, Any]:
    """Parse JSON from Claude's response"""

    try:
        # Try to extract JSON from markdown code blocks or raw JSON
        json_match = None

        # Try markdown JSON block first (Claude often wraps in ```json despite instructions)
        if '```json' in response_text:
            start = response_text.find('```json') + 7
            end = response_text.find('```', start)
            if end == -1:  # No closing ```, take rest of text
                json_match = response_text[start:].strip()
            else:
                json_match = response_text[start:end].strip()
        # Try markdown code block without json tag
        elif '```' in response_text:
            start = response_text.find('```') + 3
            end = response_text.find('```', start)
            if end == -1:  # No closing ```, take rest of text
                json_match = response_text[start:].strip()
            else:
                json_match = response_text[start:end].strip()
        # Try raw JSON
        elif '{' in response_text and '"files"' in response_text:
            start = response_text.find('{')
            end = response_text.rfind('}') + 1
            json_match = response_text[start:end]

        if json_match:
            # If JSON is incomplete (unterminated string), try to salvage it
            # by finding the last complete file entry
            try:
                return json.loads(json_match)
            except json.JSONDecodeError:
                # Try to fix incomplete JSON by finding last complete object
                if '"files": [' in json_match:
                    # Find the last complete file object
                    last_complete = json_match.rfind('},\n    {')
                    if last_complete > 0:
                        # Truncate to last complete file and close the JSON
                        json_match = json_match[:last_complete + 1] + '\n  ]\n}'
                        return json.loads(json_match)
                raise
        else:
            raise Exception('No JSON found in response')

    except json.JSONDecodeError as e:
        # Log the malformed JSON for debugging
        print(f"   ⚠️  Malformed JSON from Claude:")
        print(f"   First 500 chars: {response_text[:500]}")
        print(f"   Last 500 chars: {response_text[-500:]}")
        raise Exception(f'Failed to parse JSON: {str(e)}')


def _extract_components(files: List[Dict[str, str]]) -> List[str]:
    """Extract list of component names from generated files"""

    components = []

    for file in files:
        path = file.get('path', '')
        if path.startswith('components/') and path.endswith('.tsx'):
            # Extract component name from path (e.g., components/Hero.tsx -> Hero)
            component_name = path.split('/')[-1].replace('.tsx', '')
            components.append(component_name)

    return components
