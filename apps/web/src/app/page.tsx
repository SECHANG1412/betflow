export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl items-center px-6 py-16">
      <section>
        <p className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-blue-600">
          BetFlow
        </p>
        <h1 className="text-4xl font-bold tracking-tight sm:text-6xl">
          Betman 배당 흐름을 데이터로 읽습니다.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
          과거 유사 배당과 변화 이력을 분석해 승·무·패 통계를 제공하는 서비스입니다.
        </p>
      </section>
    </main>
  );
}
