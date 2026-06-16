import { cn } from '../../lib/utils'

export function Label({ className, ...props }) {
  return (
    <label
      className={cn('text-xs font-medium leading-none text-muted-foreground uppercase tracking-wide', className)}
      {...props}
    />
  )
}
