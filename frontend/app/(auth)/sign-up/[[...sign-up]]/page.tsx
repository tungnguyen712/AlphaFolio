import { SignUp } from "@clerk/nextjs";
import { clerkAppearance } from "@/lib/clerkAppearance";
import { DemoModeButton } from "@/components/auth/DemoModeButton";

export default function SignUpPage() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center">
      <SignUp appearance={clerkAppearance} />
      <DemoModeButton />
    </div>
  );
}
