import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { isAdmin } from '../lib/admin'

// Same shape as ProtectedRoute, but also requires the logged-in account to be
// an allow-listed admin email. Non-admins get bounced to the login page —
// this route is never linked from the public nav, so it's only reachable by
// someone who already knows the URL.
export default function AdminRoute({ children }) {
  const { currentUser, loading } = useAuth()
  if (loading) return null
  if (!currentUser || !isAdmin(currentUser)) return <Navigate to="/login" replace />
  return children
}
