export function initParticleBg(): () => void {
  const canvas = document.getElementById('particle-bg') as HTMLCanvasElement
  if (!canvas) return () => {}

  const ctx = canvas.getContext('2d')!
  if (!ctx) return () => {}

  let W = 0
  let H = 0
  const gridSpacing = 60
  const particleCount = 20
  const connectionDistance = 120

  function resize() {
    W = canvas.width = window.innerWidth
    H = canvas.height = window.innerHeight
  }
  resize()
  window.addEventListener('resize', resize)

  const particles: Array<{
    x: number; y: number; r: number; alpha: number
    speed: number; phaseX: number; phaseY: number
    ampX: number; ampY: number; periodX: number; periodY: number
  }> = []

  for (let i = 0; i < particleCount; i++) {
    particles.push({
      x: Math.random() * W, y: Math.random() * H,
      r: 1.5 + Math.random() * 1.5,
      alpha: 0.2 + Math.random() * 0.3,
      speed: 0.002 + Math.random() * 0.004,
      phaseX: Math.random() * Math.PI * 2,
      phaseY: Math.random() * Math.PI * 2,
      ampX: 10 + Math.random() * 10,
      ampY: 10 + Math.random() * 10,
      periodX: 3000 + Math.random() * 3000,
      periodY: 3000 + Math.random() * 3000,
    })
  }

  const startTime = performance.now()
  let animId = 0

  function draw() {
    ctx.clearRect(0, 0, W, H)
    const elapsed = performance.now() - startTime

    // Grid lines
    ctx.strokeStyle = 'rgba(0, 188, 212, 0.06)'
    ctx.lineWidth = 0.5
    ctx.beginPath()
    for (let x = 0; x <= W; x += gridSpacing) {
      ctx.moveTo(x, 0); ctx.lineTo(x, H)
    }
    for (let y = 0; y <= H; y += gridSpacing) {
      ctx.moveTo(0, y); ctx.lineTo(W, y)
    }
    ctx.stroke()

    // Update particles
    for (const p of particles) {
      p.x += Math.sin(elapsed * p.speed + p.phaseX) * 0.1
      p.y += Math.cos(elapsed * p.speed + p.phaseY) * 0.1
    }

    // Connection lines
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const a = particles[i], b = particles[j]
        const dx2 = (a.x + Math.sin(elapsed / a.periodX + a.phaseX) * a.ampX) -
                    (b.x + Math.sin(elapsed / b.periodX + b.phaseX) * b.ampX)
        const dy2 = (a.y + Math.cos(elapsed / a.periodY + a.phaseY) * a.ampY) -
                    (b.y + Math.cos(elapsed / b.periodY + b.phaseY) * b.ampY)
        const dist = Math.sqrt(dx2 * dx2 + dy2 * dy2)
        if (dist < connectionDistance) {
          const lineAlpha = (1 - dist / connectionDistance) * 0.15
          ctx.strokeStyle = `rgba(0, 188, 212, ${lineAlpha.toFixed(3)})`
          ctx.lineWidth = 0.5
          ctx.beginPath()
          ctx.moveTo(
            a.x + Math.sin(elapsed / a.periodX + a.phaseX) * a.ampX,
            a.y + Math.cos(elapsed / a.periodY + a.phaseY) * a.ampY
          )
          ctx.lineTo(
            b.x + Math.sin(elapsed / b.periodX + b.phaseX) * b.ampX,
            b.y + Math.cos(elapsed / b.periodY + b.phaseY) * b.ampY
          )
          ctx.stroke()
        }
      }
    }

    for (const p of particles) {
      const px = p.x + Math.sin(elapsed / p.periodX + p.phaseX) * p.ampX
      const py = p.y + Math.cos(elapsed / p.periodY + p.phaseY) * p.ampY
      ctx.fillStyle = `rgba(0, 188, 212, ${p.alpha.toFixed(3)})`
      ctx.beginPath()
      ctx.arc(px, py, p.r, 0, Math.PI * 2)
      ctx.fill()
    }

    animId = requestAnimationFrame(draw)
  }

  draw()

  return () => {
    cancelAnimationFrame(animId)
    window.removeEventListener('resize', resize)
  }
}
