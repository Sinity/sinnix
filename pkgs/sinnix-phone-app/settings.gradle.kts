// Repositories are declared here rather than per-project because the Nix build
// drives Gradle through mitm-cache: every artifact fetch is intercepted and
// recorded into deps.json, and a single declaration site keeps that lockfile
// reproducible.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "sinnix-phone"

include(":app")
