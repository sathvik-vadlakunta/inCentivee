import './Button.css'

export default function Button({
  variant = 'primary',
  icon: Icon,
  children,
  href,
  className = '',
  ...props
}) {
  const classes = `btn btn-${variant} ${className}`.trim()

  const content = (
    <>
      <span className="btn-label">{children}</span>
      {Icon && (
        <span className="btn-icon-badge">
          <Icon size={18} strokeWidth={2.5} />
        </span>
      )}
    </>
  )

  if (href) {
    return (
      <a href={href} className={classes} {...props}>
        {content}
      </a>
    )
  }

  return (
    <button className={classes} {...props}>
      {content}
    </button>
  )
}
