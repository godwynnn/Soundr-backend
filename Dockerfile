# Use an official Python runtime as a parent image
FROM python:3.12.1

# Set the working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1


RUN apt-get update


RUN pip install --upgrade pip
# Install dependencies
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Copy the project code into the container
COPY . /app/
CMD [ "daphne","core.wsgi:application" ]