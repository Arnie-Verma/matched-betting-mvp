import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function Home() {
  return (
    <main className="min-h-screen p-6 md:p-10 bg-background text-foreground">
      <div className="max-w-2xl mx-auto space-y-4">
        <h1 className="text-3xl font-semibold tracking-tight">matched-betting-mvp</h1>
        <p className="text-muted-foreground">
          Next.js + Tailwind + shadcn scaffold is live.
        </p>
        <Card className="rounded-2xl">
          <CardContent className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <div className="font-medium">Web app bootstrap</div>
                <div className="text-sm text-muted-foreground">Ready for auth & UI work next.</div>
              </div>
              <Button>It works</Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
