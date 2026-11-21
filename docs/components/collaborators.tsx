import React, { useEffect, useState } from 'react'
import styles from './collaborators.module.css'

type Collaborator = {
  html_url: string
  login: string
  avatar_url: string
}

function Collaborators() {
  const [collaborators, setCollaborators] = useState<Collaborator[] | null>(null)

  useEffect(() => {
    async function getData() {
      try {
        const response = await fetch(
          'https://api.github.com/repos/mansabov2010-jpg/instagramdownloaderbot/contributors'
        )
        const data = (await response.json()) as Collaborator[]
        setCollaborators(data)
      } catch (error) {
        console.error(error)
        setCollaborators([])
      }
    }

    void getData()
  }, [])

  if (collaborators === null) {
    return <span>Hissa qo‘shuvchilar yuklanmoqda...</span>
  }

  if (collaborators.length === 0) {
    return <span>Hozircha hissa qo‘shuvchilar haqida ma’lumot mavjud emas.</span>
  }

  return (
    <div className={styles.container}>
      <div className={styles.avatars}>
        {collaborators.map((collaborator) => (
          <div key={collaborator.login} className={styles.avatars__item}>
            <a href={collaborator.html_url} target="_blank" rel="noreferrer">
              <img
                className={styles.avatars__image}
                src={collaborator.avatar_url}
                alt={collaborator.login}
                width={40}
                height={40}
              />
            </a>
          </div>
        ))}
        <a href="https://github.com/mansabov2010-jpg/instagramdownloaderbot" target="_blank" rel="noreferrer">
          <div className={styles.more}>+</div>
        </a>
      </div>
    </div>
  )
}

export default function CollaboratorsWidget() {
  return <Collaborators />
}
