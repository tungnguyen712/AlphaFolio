import { auth } from "@clerk/nextjs/server";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { DEMO_COOKIE } from "@/lib/demo";

export default async function HomePage() {
  // Demo / recruiter bypass — no Clerk session needed
  const cookieStore = cookies();
  if (cookieStore.get(DEMO_COOKIE)?.value === "1") redirect("/research");

  const { userId } = await auth();
  if (userId) redirect("/research");
  else redirect("/sign-in");
}
