import styles from './extratox.module.css'

function ExtraTox() {
  return (
    <div className={styles.container}>
      <span className={styles.h}>Loyiha havolalari</span>
      <div className={styles.sponsors}>
        <div className={styles.bg}>
          <a
            href="https://github.com/mansabov2010-jpg/instagramdownloaderbot"
            className={styles.text}
            target="_blank"
            rel="noreferrer"
          >
            Repozitoriy
          </a>
        </div>
      </div>
      <div className={styles.bgt}>
        <a
          href="https://github.com/mansabov2010-jpg/instagramdownloaderbot/discussions"
          className={styles.text}
          target="_blank"
          rel="noreferrer"
        >
          Muhokamalar
        </a>
      </div>
    </div>
  )
}

export default ExtraTox
