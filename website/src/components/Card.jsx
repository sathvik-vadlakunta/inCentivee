import './Card.css'

const colorMap = {
  accent: 'var(--accent)',
  secondary: 'var(--secondary)',
  tertiary: 'var(--tertiary)',
  quaternary: 'var(--quaternary)',
}

export default function Card({
  icon: Icon,
  title,
  children,
  color = 'accent',
  className = '',
}) {
  const fill = colorMap[color] || colorMap.accent

  return (
    <div className={`card ${className}`} style={{ '--card-color': fill }}>
      {Icon && (
        <div className="card-icon-badge">
          <Icon size={24} strokeWidth={2.5} />
        </div>
      )}
      <h3 className="card-title">{title}</h3>
      <p className="card-body">{children}</p>
    </div>
  )
}
