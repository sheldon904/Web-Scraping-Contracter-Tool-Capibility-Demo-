export default function Home() {
  return (
    <main className="min-h-screen bg-gradient-to-b from-slate-50 to-slate-100">
      {/* Header */}
      <header className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">CR</span>
            </div>
            <span className="font-semibold text-xl">CREEP</span>
          </div>
          <nav className="flex items-center gap-6 text-sm">
            <a href="#" className="text-muted-foreground hover:text-foreground transition-colors">
              Search
            </a>
            <a href="#" className="text-muted-foreground hover:text-foreground transition-colors">
              Companies
            </a>
            <a href="#" className="text-muted-foreground hover:text-foreground transition-colors">
              About
            </a>
          </nav>
        </div>
      </header>

      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20">
        <div className="max-w-3xl mx-auto text-center">
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-6">
            Contractor Risk
            <span className="text-primary"> Evaluation</span>
          </h1>
          <p className="text-lg text-muted-foreground mb-10">
            Comprehensive risk assessment for Florida contractors. Search licenses,
            court records, BBB profiles, and UCC liens in one place.
          </p>

          {/* Search Form */}
          <div className="bg-white rounded-2xl shadow-lg p-6 border">
            <form className="space-y-4">
              <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1">
                  <label htmlFor="company" className="block text-sm font-medium text-left mb-2">
                    Company Name
                  </label>
                  <input
                    type="text"
                    id="company"
                    placeholder="Enter contractor name..."
                    className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                  />
                </div>
                <div className="w-full md:w-40">
                  <label htmlFor="state" className="block text-sm font-medium text-left mb-2">
                    State
                  </label>
                  <select
                    id="state"
                    className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all bg-white"
                  >
                    <option value="FL">Florida</option>
                  </select>
                </div>
              </div>
              <div className="flex flex-col md:flex-row gap-4">
                <div className="flex-1">
                  <label htmlFor="license" className="block text-sm font-medium text-left mb-2">
                    License Number <span className="text-muted-foreground">(optional)</span>
                  </label>
                  <input
                    type="text"
                    id="license"
                    placeholder="e.g., CGC123456"
                    className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                  />
                </div>
                <div className="w-full md:w-40">
                  <label htmlFor="city" className="block text-sm font-medium text-left mb-2">
                    City <span className="text-muted-foreground">(optional)</span>
                  </label>
                  <input
                    type="text"
                    id="city"
                    placeholder="Miami"
                    className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
                  />
                </div>
              </div>
              <button
                type="submit"
                className="w-full bg-primary text-primary-foreground py-3 px-6 rounded-lg font-medium hover:bg-primary/90 transition-colors"
              >
                Search Contractor
              </button>
            </form>
          </div>
        </div>
      </section>

      {/* Data Sources */}
      <section className="container mx-auto px-4 py-16">
        <h2 className="text-2xl font-semibold text-center mb-10">Data Sources</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
          {[
            {
              title: "FL DBPR Licenses",
              description: "License status, disciplinary actions, expiration dates",
              icon: "📋",
            },
            {
              title: "BBB Profiles",
              description: "Ratings, accreditation, complaint history",
              icon: "⭐",
            },
            {
              title: "Federal Courts",
              description: "Lawsuits, bankruptcy filings, case history",
              icon: "⚖️",
            },
            {
              title: "UCC Liens",
              description: "Secured transactions, financial obligations",
              icon: "📄",
            },
          ].map((source) => (
            <div
              key={source.title}
              className="bg-white rounded-xl p-6 border shadow-sm hover:shadow-md transition-shadow"
            >
              <div className="text-3xl mb-4">{source.icon}</div>
              <h3 className="font-semibold mb-2">{source.title}</h3>
              <p className="text-sm text-muted-foreground">{source.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Risk Score Preview */}
      <section className="container mx-auto px-4 py-16">
        <div className="max-w-4xl mx-auto bg-white rounded-2xl shadow-lg border overflow-hidden">
          <div className="bg-slate-50 px-6 py-4 border-b">
            <h2 className="text-lg font-semibold">Risk Assessment Preview</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {[
                { label: "Licensing", weight: "35%", color: "bg-blue-500" },
                { label: "Reputation", weight: "25%", color: "bg-green-500" },
                { label: "Litigation", weight: "25%", color: "bg-orange-500" },
                { label: "Financial", weight: "15%", color: "bg-purple-500" },
              ].map((category) => (
                <div key={category.label} className="text-center">
                  <div
                    className={`w-16 h-16 ${category.color} rounded-full mx-auto mb-3 flex items-center justify-center text-white font-bold`}
                  >
                    {category.weight}
                  </div>
                  <p className="font-medium">{category.label}</p>
                  <p className="text-xs text-muted-foreground">Risk Weight</p>
                </div>
              ))}
            </div>
            <p className="text-center text-muted-foreground mt-6 text-sm">
              Risk scores are calculated using a weighted algorithm across four key categories.
            </p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t bg-white mt-16">
        <div className="container mx-auto px-4 py-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 bg-primary rounded flex items-center justify-center">
                <span className="text-white font-bold text-xs">CR</span>
              </div>
              <span className="font-medium">CREEP</span>
              <span className="text-muted-foreground text-sm">
                Contractor Risk Evaluation and Exploration Platform
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              Data sourced from public records. Not legal advice.
            </p>
          </div>
        </div>
      </footer>
    </main>
  );
}
