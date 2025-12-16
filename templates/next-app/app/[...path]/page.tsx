import { BuilderComponent, builder } from '@builder.io/react';
import { fetchBuilderContent } from '@/lib/builder';
import { notFound } from 'next/navigation';

// Initialize Builder.io
builder.init(process.env.NEXT_PUBLIC_BUILDER_API_KEY!);

interface PageProps {
  params: {
    path?: string[];
  };
}

export default async function Page({ params }: PageProps) {
  const urlPath = '/' + (params.path?.join('/') || '');
  const spaceMode = process.env.BUILDER_SPACE_MODE || 'DEDICATED';

  // Determine model name based on space mode
  // IMPORTANT: Builder.io auto-generates hyphenated unique identifiers
  const model = spaceMode === 'SHARED' ? 'client-page' : 'page';

  try {
    const content = await fetchBuilderContent(model, urlPath);

    if (!content) {
      notFound();
    }

    return (
      <>
        <BuilderComponent model={model} content={content} />
      </>
    );
  } catch (error) {
    console.error('Error fetching Builder.io content:', error);
    notFound();
  }
}

/**
 * Generate static paths for all pages in Builder.io
 * This enables static site generation (SSG) for better performance
 */
export async function generateStaticParams() {
  const spaceMode = process.env.BUILDER_SPACE_MODE || 'DEDICATED';
  const model = spaceMode === 'SHARED' ? 'client-page' : 'page';

  try {
    // Note: For shared spaces, this will be called per client deployment
    // The middleware ensures client_slug isolation at runtime
    const pages = await builder.getAll(model, {
      options: { noTargeting: true },
      limit: 100
    });

    return pages.map((page) => ({
      path: page.data?.urlPath?.split('/').filter(Boolean) || []
    }));
  } catch (error) {
    console.error('Error generating static params:', error);
    return [];
  }
}
