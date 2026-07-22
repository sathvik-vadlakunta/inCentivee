import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { useEffect } from 'react'
import { AuthProvider } from './context/AuthContext'
import { applyCosmetics } from './lib/shop'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Home from './pages/Home'
import ResourcesPage from './pages/Resources'
import CompoundInterest from './pages/CompoundInterest'
import LoanCalculator from './pages/LoanCalculator'
import RetirementCalculator from './pages/RetirementCalculator'
import AboutPage from './pages/About'
import ArticlesPage from './pages/Articles'
import ArticlePage from './pages/ArticlePage'
import QuizzesPage from './pages/Quizzes'
import QuizTaker from './pages/QuizTaker'
import QuizCreate from './pages/QuizCreate'
import Login from './pages/Login'
import Learn from './pages/Learn'
import Progress from './pages/Progress'
import UnitPage from './pages/UnitPage'
import Admin from './pages/Admin'
import AdminRoute from './components/AdminRoute'
import CoinFlyLayer from './components/CoinFlyLayer'
import './App.css'

export default function App() {
  useEffect(() => { applyCosmetics() }, [])

  return (
    <>
    {/* Shared coin gradient — referenced via url(#coin-grad) in any SVG on the page */}
    <svg style={{position:'absolute',width:0,height:0,overflow:'hidden'}} aria-hidden="true">
      <defs>
        <radialGradient id="coin-grad" cx="0.35" cy="0.28" r="0.72" gradientUnits="objectBoundingBox">
          <stop offset="0%"   stopColor="#FFFBEB"/>
          <stop offset="28%"  stopColor="#FCD34D"/>
          <stop offset="65%"  stopColor="#F59E0B"/>
          <stop offset="100%" stopColor="#DC6803"/>
        </radialGradient>
      </defs>
    </svg>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="resources" element={<ResourcesPage />} />
            <Route path="compound-interest" element={<CompoundInterest />} />
            <Route path="loan-calculator" element={<LoanCalculator />} />
            <Route path="retirement-calculator" element={<RetirementCalculator />} />
            <Route path="about" element={<AboutPage />} />
            <Route path="articles" element={<ArticlesPage />} />
            <Route path="articles/:id" element={<ArticlePage />} />
            <Route path="quizzes" element={<QuizzesPage />} />
            <Route path="quizzes/create" element={<QuizCreate />} />
            <Route path="quizzes/edit/:id" element={<QuizCreate />} />
            <Route path="quizzes/:code" element={<QuizTaker />} />
            <Route path="login" element={<Login />} />
            <Route path="learn" element={<Learn />} />
            <Route path="progress" element={<Progress />} />
            <Route path="learn/unit/:unitId" element={<UnitPage />} />
            <Route path="admin" element={<AdminRoute><Admin /></AdminRoute>} />
          </Route>
        </Routes>
        <CoinFlyLayer />
      </AuthProvider>
    </BrowserRouter>
    </>
  )
}
