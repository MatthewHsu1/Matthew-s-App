# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Copy solution and project files first (for better caching)
COPY FinancialApp.Backend.sln ./
COPY src/FinancialApp.Api/*.csproj ./src/FinancialApp.Api/
COPY src/FinancialApp.Application/*.csproj ./src/FinancialApp.Application/
COPY src/FinancialApp.Domain/*.csproj ./src/FinancialApp.Domain/
COPY src/FinancialApp.Infrastructure/*.csproj ./src/FinancialApp.Infrastructure/

# Restore dependencies
RUN dotnet restore

# Copy the rest of the code
COPY . .

# Build and Publish
WORKDIR /src/src/FinancialApp.Api
RUN dotnet publish -c Release -o /app/publish

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app
EXPOSE 8080
COPY --from=build /app/publish .
ENTRYPOINT ["dotnet", "FinancialApp.Api.dll"]

