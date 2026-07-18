import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
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
import UnitPage from './pages/UnitPage'
import Admin from './pages/Admin'
import AdminRoute from './components/AdminRoute'
import CoinFlyLayer from './components/CoinFlyLayer'
import './App.css'

export default function App() {
  return (
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
            <Route path="learn/unit/:unitId" element={<UnitPage />} />
            <Route path="admin" element={<AdminRoute><Admin /></AdminRoute>} />
          </Route>
        </Routes>
        <CoinFlyLayer />
      </AuthProvider>
    </BrowserRouter>
  )
}
