import { useEffect, useState, useRef } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import { motion, AnimatePresence } from 'framer-motion'
import { useWebSocketStore } from '../../store/websocketStore'
import { useAuthStore } from '../../store/authStore'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { user } = useAuthStore()
  const { connect, setClientId, disconnect } = useWebSocketStore()

  const isMounted = useRef(false)

  useEffect(() => {
    if (user?.id) {
      isMounted.current = true
      setClientId(`global-${user.id}`)
      connect()
    }
    
    // Close sidebar on mobile when navigating
    if (window.innerWidth < 1024) {
      setSidebarOpen(false)
    }
    
    return () => {
      // Small timeout to prevent the "closed before established" error 
      // during React StrictMode double-mount/unmount cycles
      setTimeout(() => {
        if (!isMounted.current) {
          disconnect()
        }
      }, 100)
      isMounted.current = false
    }
  }, [user?.id, connect, setClientId, disconnect])

  return (
    <div className="flex h-screen bg-[#05050a] text-white overflow-hidden relative font-jakarta">
      {/* Dynamic Background VFX */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-sky-600/5 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[30%] h-[30%] bg-purple-600/5 blur-[100px] rounded-full" />
        <div className="absolute inset-0 grid-pattern opacity-10" />
      </div>

      <Sidebar isOpen={sidebarOpen} setIsOpen={setSidebarOpen} />
      
      {/* Mobile Backdrop */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-30 lg:hidden"
          />
        )}
      </AnimatePresence>

      <div className="flex-1 flex flex-col overflow-hidden min-w-0 relative">
        <TopBar onMenuClick={() => setSidebarOpen(true)} sidebarOpen={sidebarOpen} />
        
        <main className="flex-1 overflow-auto custom-scrollbar relative">
          {/* Content Wrapper with padding */}
          <div className="p-8 max-w-[1600px] mx-auto min-h-full">
            <AnimatePresence mode="wait">
              <motion.div
                key={window.location.pathname}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
              >
                <Outlet />
              </motion.div>
            </AnimatePresence>
          </div>
        </main>
      </div>

      {/* Global Modal Container */}
      <div id="modal-root" />
    </div>
  )
}
