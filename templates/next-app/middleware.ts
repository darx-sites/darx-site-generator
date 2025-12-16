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

  if (host.includes('localhost')) {
    return process.env.NEXT_PUBLIC_CLIENT_SLUG || 'development';
  }

  const parts = host.split('.');
  if (parts.length < 3) {
    return null;
  }

  const subdomain = parts[0];

  // Validate slug format
  if (!/^[a-z0-9-]+$/.test(subdomain)) {
    return null;
  }

  return subdomain;
}

export const config = {
  matcher: '/:path*',
};
