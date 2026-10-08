import { SignIn } from "@clerk/nextjs";
import { clerkAppearance } from "@/lib/clerkAppearance";
import { DemoModeButton } from "@/components/auth/DemoModeButton";

export default function SignInPage() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center">
      <SignIn appearance={clerkAppearance} />
      <DemoModeButton />
    </div>
  );
}
