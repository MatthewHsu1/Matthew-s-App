using Backend.Api.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

builder.AddApi();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

app.UseApi();

app.Run();
