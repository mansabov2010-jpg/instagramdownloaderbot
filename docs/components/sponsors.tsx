import styles from './sponsors.module.css'

function Sponsors() {
  return (
    <div className={styles.container}>
      <div className={styles.sponsor_card}>
        <div className={styles.sponsor_cardh}>
          <div className={styles.sponsor_links}>
            <a
              href="https://github.com/mansabov2010-jpg/instagramdownloaderbot"
              target="_blank"
              rel="noreferrer"
            >
              Loyiha repozitoriysi ↗
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function SponsorsWidget() {
  return <Sponsors />
}
