import { NextRequest, NextResponse } from 'next/server';

export function middleware(request: NextRequest) {
  const host = request.headers.get('host') || '';

  // Extract client_slug from hostname
  // Format: {client-slug}.darx.site
  const clientSlug = extractClientSlug(host);

  if (!clientSlug) {
    return new NextResponse('Invalid hostname', { status: 400 });
  }

  // Inject client_slug into request headers for downstream use
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set('x-client-slug', clientSlug);

  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

function extractClientSlug(host: string): string | null {
  // acme.darx.site → acme
  // acme-company.darx.site → acme-company
  // localhost:3000 → development (for local dev)
  // test-client-14.vercel.app → test-client-14
  // test-client-14-hash123-team.vercel.app → test-client-14 (Vercel preview)

  if (host.includes('localhost')) {
    return process.env.NEXT_PUBLIC_CLIENT_SLUG || 'development';
  }

  const parts = host.split('.');
  if (parts.length < 3) {
    return null;
  }

  let subdomain = parts[0];

  // Handle Vercel preview URLs: project-hash-team.vercel.app
  // Extract just the project name (everything before first hash-like segment)
  if (host.includes('.vercel.app')) {
    // Vercel preview URLs have format: {project}-{hash}-{team}.vercel.app
    // Production URLs have format: {project}.vercel.app
    // We need to extract just the {project} part

    // Split subdomain by hyphens
    const segments = subdomain.split('-');

    // If more than 3 segments, it's likely a preview URL with hash
    // Example: test-client-14-kszvvxbwu-digitalarchitexs-projects
    // We want: test-client-14
    if (segments.length > 3) {
      // Find where the hash-like segment starts (8+ char alphanumeric string)
      const hashIndex = segments.findIndex(seg =>
        seg.length >= 8 && /^[a-z0-9]+$/.test(seg)
      );

      if (hashIndex > 0) {
        // Take everything before the hash
        subdomain = segments.slice(0, hashIndex).join('-');
      }
    }
  }

  // Validate slug format
  if (!/^[a-z0-9-]+$/.test(subdomain)) {
    return null;
  }

  return subdomain;
}

export const config = {
  matcher: '/:path*',
};
