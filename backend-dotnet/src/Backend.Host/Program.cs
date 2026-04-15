using Backend.Api.DependencyInjection;
using Backend.Application.DependencyInjection;
using Backend.Infrastructure.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

builder.AddApi();
builder.Services.AddApplication(builder.Configuration);
builder.Services.AddInfrastructure(builder.Configuration);

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi().AllowAnonymous();
}

app.UseApi();

app.Run();
