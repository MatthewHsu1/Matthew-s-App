# Stage 1: Build
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src

# Copy solution and project files first (for better caching)
COPY Backend.sln ./
COPY src/Backend.Api/*.csproj ./src/Backend.Api/
COPY src/Backend.Application/*.csproj ./src/Backend.Application/
COPY src/Backend.Domain/*.csproj ./src/Backend.Domain/
COPY src/Backend.Infrastructure/*.csproj ./src/Backend.Infrastructure/

# Restore dependencies
RUN dotnet restore

# Copy the rest of the code
COPY . .

# Build and Publish
WORKDIR /src/src/Backend.Api
RUN dotnet publish -c Release -o /app/publish

# Stage 2: Runtime
FROM mcr.microsoft.com/dotnet/aspnet:10.0 AS final
WORKDIR /app
EXPOSE 8080
COPY --from=build /app/publish .
ENTRYPOINT ["dotnet", "Backend.Api.dll"]

