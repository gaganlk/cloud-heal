import { useState, useEffect } from 'react'
import { Bell, Check, ExternalLink, X, Info, AlertTriangle, CheckCircle, AlertCircle } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import { useWebSocket } from '../../hooks/useWebSocket'
import API from '../../api/auth'
import { formatDistanceToNow } from 'date-fns'
import { motion, AnimatePresence } from 'framer-motion'
import { Link } from 'react-router-dom'

export default function NotificationPanel({ isOpen, onClose }) {
  const { user, token } = useAuthStore()
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(false)
  const { lastMessage } = useWebSocket()

  const fetchNotifications = async () => {
    try {
      setLoading(true)
      const res = await API.get('/notifications/')
      setNotifications(res.data)
    } catch (err) {
      console.error('Failed to fetch notifications', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen) fetchNotifications()
  }, [isOpen])

  useEffect(() => {
    if (lastMessage?.type === 'new_notification') {
      setNotifications(prev => [lastMessage.data, ...prev])
    }
  }, [lastMessage])

  const markAsRead = async (id) => {
    try {
      await API.put(`/notifications/${id}/read`, {})
      setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n))
    } catch (err) {
      console.error('Failed to mark as read', err)
    }
  }

  const markAllAsRead = async () => {
    try {
      await API.put(`/notifications/read-all`, {})
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
    } catch (err) {
      console.error('Failed to mark all as read', err)
    }
  }

  const getIcon = (type) => {
    switch (type) {
      case 'success': return <CheckCircle className="w-4 h-4 text-emerald-400" />
      case 'warning': return <AlertTriangle className="w-4 h-4 text-amber-400" />
      case 'error': return <AlertCircle className="w-4 h-4 text-red-400" />
      default: return <Info className="w-4 h-4 text-sky-400" />
    }
  }

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={onClose} />
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            className="absolute top-full right-0 mt-2 w-80 md:w-96 glass-dark border border-white/10 rounded-2xl shadow-2xl z-50 overflow-hidden flex flex-col max-h-[500px]"
          >
            {/* Header */}
            <div className="p-4 border-b border-white/5 flex items-center justify-between">
              <h3 className="font-semibold text-white">Notifications</h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={markAllAsRead}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-all"
                  title="Mark all as read"
                >
                  <Check className="w-4 h-4" />
                </button>
                <button
                  onClick={onClose}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-all"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* List */}
            <div className="flex-1 overflow-auto">
              {loading && notifications.length === 0 ? (
                <div className="p-8 text-center space-y-3">
                  <div className="w-8 h-8 border-2 border-sky-500 border-t-transparent rounded-full animate-spin mx-auto" />
                  <p className="text-xs text-slate-500">Loading alerts...</p>
                </div>
              ) : notifications.length === 0 ? (
                <div className="p-12 text-center opacity-40">
                  <Bell className="w-8 h-8 mx-auto mb-2" />
                  <p className="text-sm">No notifications yet</p>
                </div>
              ) : (
                <div className="divide-y divide-white/5">
                  {notifications.map((n) => (
                    <motion.div
                      key={n.id}
                      layout
                      className={`p-4 hover:bg-white/5 transition-all group ${!n.is_read ? 'bg-sky-500/5' : ''}`}
                    >
                      <div className="flex gap-3">
                        <div className={`mt-1 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-white/5`}>
                          {getIcon(n.type)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                             <h4 className={`text-sm font-medium leading-tight ${!n.is_read ? 'text-white' : 'text-slate-300'}`}>
                              {n.title}
                            </h4>
                            {!n.is_read && (
                              <button
                                onClick={() => markAsRead(n.id)}
                                className="opacity-0 group-hover:opacity-100 p-1 text-sky-400 transition-all"
                                title="Mark read"
                              >
                                <Check className="w-3 h-3" />
                              </button>
                            )}
                          </div>
                          <p className="text-xs text-slate-500 mt-1 line-clamp-2">{n.message}</p>
                          <div className="mt-2 flex items-center justify-between">
                            <span className="text-[10px] text-slate-600">
                              {formatDistanceToNow(new Date(n.created_at), { addSuffix: true })}
                            </span>
                            {n.link && (
                              <Link
                                to={n.link}
                                onClick={onClose}
                                className="flex items-center gap-1 text-[10px] text-sky-400 hover:underline"
                              >
                                View Details <ExternalLink className="w-2.5 h-2.5" />
                              </Link>
                            )}
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-3 bg-white/5 border-t border-white/5 text-center">
              <Link
                to="/timeline"
                onClick={onClose}
                className="text-xs text-slate-400 hover:text-white transition-all font-medium"
              >
                View all activities
              </Link>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
