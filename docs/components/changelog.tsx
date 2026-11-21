import React, { useEffect, useState } from 'react'
import styles from './changelog.module.css'

type CommitItem = {
  html_url: string
  commit: {
    message: string
    author?: { date?: string }
    comment_count?: number
    verification?: { verified?: boolean }
  }
  author?: {
    html_url?: string
    avatar_url?: string
  } | null
}

function formatDate(date?: string) {
  if (!date) return 'Noma’lum sana'
  return new Date(date).toDateString()
}

function ChangeLog() {
  const [commits, setCommits] = useState<CommitItem[] | null>(null)

  useEffect(() => {
    async function getData() {
      try {
        const response = await fetch(
          'https://api.github.com/repos/mansabov2010-jpg/instagramdownloaderbot/commits'
        )
        const data = (await response.json()) as CommitItem[]
        setCommits(data)
      } catch (error) {
        console.error(error)
        setCommits([])
      }
    }

    void getData()
  }, [])

  if (commits === null) {
    return <span>Commitlar yuklanmoqda...</span>
  }

  if (commits.length === 0) {
    return <span>Hozircha o‘zgarishlar tarixi (changelog) mavjud emas.</span>
  }

  return (
    <div className={styles.container}>
      <div className="books">
        {commits.map((commitItem, index) => (
          <div key={index} className={styles.tmtimelineitem}>
            <h2>
              Commit <span className={styles.uktextmuted}>({formatDate(commitItem.commit.author?.date)})</span>
            </h2>
            <div className={styles.tmtimelineentry}>
              <div className={styles.tmtimelineentrylabel}>
                <span className={styles.ukbadge}>
                  {commitItem.commit.verification?.verified ? (
                    <span className={styles.ukbadgesuccess}>Tasdiqlangan</span>
                  ) : (
                    <span className={styles.ukbadgedanger}>Tasdiqlanmagan</span>
                  )}
                </span>
              </div>
              <div className={styles.tmtimelineentrydata}>
                <a href={commitItem.html_url}>{commitItem.commit.message}</a>
              </div>
            </div>
            <div className={styles.iconset}>
              <div className={styles.bicon}>
                Muallif:{' '}
                {commitItem.author?.html_url && commitItem.author.avatar_url ? (
                  <a href={commitItem.author.html_url}>
                    <img
                      className={styles.avatar}
                      alt="GitHub avatari"
                      src={commitItem.author.avatar_url}
                      width={25}
                      height={25}
                    />
                  </a>
                ) : (
                  'Noma’lum'
                )}
              </div>
              <div className={styles.bicon}>
                Izohlar: {commitItem.commit.comment_count ?? 0}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ChangelogWidget() {
  return <ChangeLog />
}
