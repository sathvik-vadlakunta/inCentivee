import Navbar from './components/Navbar'
import Hero from './components/Hero'
import Features from './components/Features'
import Resources from './components/Resources'
import CTA from './components/CTA'
import Footer from './components/Footer'
import './App.css'

export default function App() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <Features />
        <Resources />
        <CTA />
      </main>
      <Footer />
    </>
  )
}
