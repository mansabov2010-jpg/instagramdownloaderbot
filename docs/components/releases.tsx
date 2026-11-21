import React, { useEffect, useState } from 'react'
import styles from './releases.module.css'

type ReleaseItem = {
  html_url: string
  tag_name: string
  published_at?: string
  draft?: boolean
  prerelease?: boolean
  body?: string
}

function formatDate(date?: string) {
  if (!date) return 'Noma’lum sana'
  return new Date(date).toDateString()
}

function Releases() {
  const [releases, setReleases] = useState<ReleaseItem[] | null>(null)

  useEffect(() => {
    async function getData() {
      try {
        const response = await fetch(
          'https://api.github.com/repos/mansabov2010-jpg/instagramdownloaderbot/releases'
        )
        const data = (await response.json()) as ReleaseItem[]
        setReleases(data)
      } catch (error) {
        console.error(error)
        setReleases([])
      }
    }

    void getData()
  }, [])

  if (releases === null) {
    return <span>Relizlar yuklanmoqda...</span>
  }

  if (releases.length === 0) {
    return <span>Hozircha relizlar haqida ma’lumot mavjud emas.</span>
  }

  return (
    <div className={styles.container}>
      <div className="books">
        {releases.map((release) => (
          <div key={release.tag_name} className={styles.tmtimelineitem}>
            <span>
              <a href={release.html_url}>{release.tag_name}</a>{' '}
              <span className={styles.uktextmuted}>({formatDate(release.published_at)})</span>
            </span>
            <div className={styles.tmtimelineentry}>
              <div className={styles.tmtimelineentrylabel}>
                <span className={styles.ukbadge}>
                  {release.draft ? (
                    <span className={styles.ukbadgewarning}>Qoralama</span>
                  ) : release.prerelease ? (
                    <span className={styles.ukbadgewarning}>Sinov versiyasi</span>
                  ) : (
                    <span className={styles.ukbadgesuccess}>Reliz</span>
                  )}
                </span>
              </div>
              <div className={styles.tmtimelineentrydata}>
                <p>{(release.body || '').split(' ').slice(0, 40).join(' ')}</p>
              </div>
              <a href={release.html_url}>
                <span className={styles.readmore}>Batafsil ...</span>
              </a>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ReleasesWidget() {
  return <Releases />
}
