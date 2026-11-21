import React from 'react'
import { DocsThemeConfig } from 'nextra-theme-docs'

const config: DocsThemeConfig = {
  head: (
    <>
      <meta charSet="UTF-8" />
      <meta name="author" content="mansabov2010-jpg" />
      <meta name="keywords" content="telegram, telegram bot, aiogram, yt-dlp, instagram yuklovchi, youtube, tiktok" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <meta property="og:title" content="Instagram Downloader Bot hujjatlari" />
      <meta
        property="og:description"
        content="aiogram asosidagi Instagram, YouTube va TikTok video yuklovchi bot hujjatlari."
      />
      <link rel="shortcut icon" href="/favicon.ico" />
      <title>Instagram Downloader Bot hujjatlari</title>
    </>
  ),
  banner: {
    key: 'aiogram-migration',
    text: (
      <a
        href="https://github.com/mansabov2010-jpg/instagramdownloaderbot"
        target="_blank"
        rel="noreferrer"
      >
        Bot endi ildiz (root) loyiha tuzilmasi bilan aiogram asosida ishlaydi.
      </a>
    ),
  },
  logo: <span>Instagram Downloader Bot</span>,
  project: {
    link: 'https://github.com/mansabov2010-jpg/instagramdownloaderbot',
  },
  chat: {
    link: 'https://github.com/mansabov2010-jpg/instagramdownloaderbot/discussions',
    icon: <span>GitHub</span>,
  },
  docsRepositoryBase: 'https://github.com/mansabov2010-jpg/instagramdownloaderbot/tree/main/docs',
  footer: {
    component: null,
  },
  faviconGlyph: '(o)'
}

export default config
