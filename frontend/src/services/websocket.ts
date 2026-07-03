type MessageHandler = (data: any) => void

class WebSocketService {
  private ws: WebSocket | null = null
  private handlers = new Map<string, Set<MessageHandler>>()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private url: string = ''
  private isConnected = false

  connect(token: string) {
    this.url = `/api/v1/ws?token=${token}`
    this.createConnection()
  }

  private createConnection() {
    if (this.ws) {
      this.ws.close()
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const fullUrl = `${protocol}//${host}${this.url}`

    this.ws = new WebSocket(fullUrl)

    this.ws.onopen = () => {
      this.isConnected = true
      this.startPing()
      // Subscribe to default channels
      this.send({ type: 'subscribe', channels: ['alerts:*', 'agents:*', 'system:announcement'] })
    }

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        this.dispatch(msg.type, msg.data || msg)
      } catch {
        // ignore parse errors
      }
    }

    this.ws.onclose = () => {
      this.isConnected = false
      this.stopPing()
      this.scheduleReconnect()
    }

    this.ws.onerror = () => {
      this.isConnected = false
    }
  }

  private send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  private startPing() {
    this.pingTimer = setInterval(() => {
      this.send({ type: 'ping' })
    }, 30000)
  }

  private stopPing() {
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.createConnection()
    }, 5000)
  }

  on(event: string, handler: MessageHandler) {
    if (!this.handlers.has(event)) {
      this.handlers.set(event, new Set())
    }
    this.handlers.get(event)!.add(handler)
  }

  off(event: string, handler: MessageHandler) {
    this.handlers.get(event)?.delete(handler)
  }

  private dispatch(event: string, data: any) {
    this.handlers.get(event)?.forEach((handler) => {
      try {
        handler(data)
      } catch {
        // handler error
      }
    })
  }

  disconnect() {
    this.stopPing()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.isConnected = false
  }
}

export const wsService = new WebSocketService()
export default wsService
