interface EmptyStateProps {
  title: string
  description: string
  action?: React.ReactNode
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-gray-200 py-16 px-8 text-center">
      <div className="text-4xl" aria-hidden="true">
        &#x1F50D;
      </div>
      <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
      <p className="max-w-sm text-sm text-gray-500">{description}</p>
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
