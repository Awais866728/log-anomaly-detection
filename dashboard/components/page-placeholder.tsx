import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export function PagePlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <Card className="border-dashed">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
    </Card>
  )
}
